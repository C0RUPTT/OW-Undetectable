"""Entry point: python -m ow_assist (or run.bat)"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from . import commands
from .data import (ROOT, DEFAULT_ABILITIES, DEFAULT_HISTORY, DEFAULT_SETTINGS, apply_switches,
                   load_abilities, load_library, load_settings)
from .speech import Speaker
from .tracker import Tracker


class Controller:
    def __init__(self, data, settings, speaker: Speaker, tilt=None, log=print):
        self.data = data
        self.tilt = tilt
        self._undo_owners: list[str] = []  # who handled each undoable action, newest last
        self.settings = settings
        self.speaker = speaker
        self.log = log
        self.tracker = Tracker(data, settings["call_lag_seconds"])
        self._lock = threading.Lock()
        self._fired_partial: str | None = None
        self.last_heard = ""

    def on_text(self, text: str, final: bool, conf: float | None = None) -> None:
        """Called from the voice thread with partial and final recognition results.

        conf is the lowest word confidence of a final result, when the recognizer gives one.
        """
        cmd = commands.parse(text, self.data)
        if final and text.strip():
            shown = f" ({conf:.2f})" if conf is not None else ""
            self.log(f"heard: {text}{shown}" + ("" if cmd else "  -> not a command"))
        if final and cmd and conf is not None and conf < self.settings.get("min_confidence", 0):
            self.log(f"  -> skipped, below min_confidence {self.settings['min_confidence']}")
            self._fired_partial = None
            return
        if not final:
            # Fire as soon as a partial result is already a full command: shaves the
            # end-of-utterance wait off every call. The final result is then deduped.
            if self.settings["fire_on_partial"] and cmd and text != self._fired_partial:
                self._fired_partial = text
                self._run(cmd, text)
            return
        already = self._fired_partial
        self._fired_partial = None
        if cmd and text != already:
            self._run(cmd, text)

    def _run(self, cmd, text: str) -> None:
        self.last_heard = text
        if cmd.kind in commands.TILT_KINDS:
            if self.tilt is None:
                return
            with self._lock:
                lines = self.tilt.handle(cmd, time.time())
                if cmd.kind == "result":
                    self._undo_owners.append("tilt")
            self._say(lines)
            return
        with self._lock:
            if cmd.kind == "undo" and self._undo_owners and self._undo_owners[-1] == "tilt":
                self._undo_owners.pop()
                lines = self.tilt.undo()
                events = []
            else:
                if cmd.kind == "undo" and self._undo_owners:
                    self._undo_owners.pop()
                events = self.tracker.apply(cmd, time.monotonic())
                if events[0].kind in ("used", "cancelled", "reset"):
                    self._undo_owners.append("tracker")
                lines = []
        self._say(lines)
        for e in events:
            self.speaker.handle(e)
            self.log(f"[{e.kind}] {text}")

    def _say(self, lines: list[str]) -> None:
        for line in lines:
            self.speaker.say(line)
            self.log(f"[say] {line}")

    def game_started(self) -> None:
        if self.tilt:
            with self._lock:
                self.tilt.start_session(time.time())
            self.log("[session] game started")

    def game_stopped(self) -> None:
        if self.tilt:
            with self._lock:
                lines = self.tilt.end_session(time.time())
            self._say(lines)
            self.log("[session] game closed")

    def tick(self):
        with self._lock:
            now = time.monotonic()
            events = self.tracker.poll(now)
            status = self.tracker.status(now)
            lines = self.tilt.check(time.time()) if self.tilt else []
        for e in events:
            self.speaker.handle(e)
            self.log(f"[{e.kind}] {self.data.get(e.ability_id).label}")
        self._say(lines)
        return status, self.last_heard

    def ult_snapshot(self) -> dict:
        """Ult timers for the phone view, in data-file order so rows don't jump around."""
        with self._lock:
            status = self.tracker.status(time.monotonic())
            session = self.tilt.snapshot(time.time()) if self.tilt else None
        order = {aid: i for i, aid in enumerate(self.data.abilities)}
        ults = sorted(status.ults, key=lambda x: order[x[0].id])
        return {"ults": [{"id": a.id, "hero": a.hero, "name": a.name, "elapsed": round(e, 2)}
                         for a, e in ults],
                "session": session}

    def shutdown(self) -> None:
        if self.tilt:
            with self._lock:
                self.tilt.end_session(time.time())
        self.speaker.close()


def format_library(library) -> str:
    lines = []
    for kind, title in (("cooldown", "COOLDOWNS"), ("ult", "ULTS")):
        lines.append(f"\n{title}  (use any of these names in turn_on or turn_off in my_settings.json)")
        for a in sorted((a for a in library if a.kind == kind), key=lambda a: (not a.enabled, a.hero)):
            cd = f" {a.cooldown:g}s" if kind == "cooldown" else ""
            say = " / ".join(a.aliases)
            lines.append(f"  [{'ON ' if a.enabled else 'off'}] {say:<28} {a.hero} {a.name}{cd}")
    return "\n".join(lines).lstrip("\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ow_assist", description="Voice-driven cooldown tracker")
    p.add_argument("--model", help="path to an unzipped Vosk model folder")
    p.add_argument("--text", action="store_true", help="type commands instead of speaking (testing)")
    p.add_argument("--window", action="store_true", help="also show the status window (ult timers)")
    p.add_argument("--phone", action="store_true", help="serve the ult view to your phone")
    p.add_argument("--mute", action="store_true", help="no speech (testing)")
    p.add_argument("--device", help="microphone device name or index (see --list-devices)")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--list-abilities", action="store_true",
                   help="show every ability, whether it's on, and what to say")
    p.add_argument("--abilities", default=str(DEFAULT_ABILITIES))
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    p.add_argument("--history", default=str(DEFAULT_HISTORY), help="where game results are stored")
    p.add_argument("--stats", action="store_true", help="print your stats and exit")
    args = p.parse_args(argv)

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return 0
    if args.stats:
        from .stats import report
        from .tilt import Store
        print(report(Store(args.history).games()))
        return 0
    if args.list_abilities:
        s = load_settings(args.settings)
        library = apply_switches(load_library(args.abilities), s["turn_on"], s["turn_off"],
                                 s["cooldowns"])
        print(format_library(library))
        return 0
    settings = load_settings(args.settings)
    # Command-line options win; otherwise use model/device/phone from your settings.
    model = args.model or str(ROOT / settings["model"])
    device_arg = args.device if args.device is not None else settings["device"]
    if not args.text and not Path(model).is_dir():
        p.error(f"speech model folder not found: {model}\n"
                "Download it (see README) or point 'model' in my_settings.json at it.")
    data = load_abilities(args.abilities, settings["turn_on"], settings["turn_off"],
                          settings["cooldowns"])
    print(f"Tracking {len(data.abilities)} abilities. See them all with --list-abilities.")
    if settings["push_to_talk"]:
        from .ptt import parse_binding
        parse_binding(settings["push_to_talk"])  # fail now, not mid-match
    from .tilt import Store, TiltTracker
    tilt = TiltTracker(Store(args.history), settings["warn_after_losses"],
                       settings["stop_after_losses"], settings["long_session_minutes"],
                       settings["session_gap_minutes"])
    speaker = Speaker(data, enabled=not args.mute, rate=settings["speech_rate"])
    controller = Controller(data, settings, speaker, tilt)

    from .watcher import GameWatcher
    GameWatcher(settings["game_process"], controller.game_started, controller.game_stopped,
                settings["session_end_grace_seconds"]).start()

    if args.phone or settings["phone"]:
        from .phone import PhoneServer
        phone = PhoneServer(controller.ult_snapshot, port=settings["phone_port"])
        phone.start()
        print(f"Phone view: open {phone.url} on your phone (same Wi-Fi)")

    if args.text:
        def read_stdin():
            print("Type commands (e.g. 'nade', 'cancel nade', 'undo', 'reset'):")
            for line in sys.stdin:
                if not commands.parse(line, data):
                    print("  not a command")
                controller.on_text(line.strip(), True)
        threading.Thread(target=read_stdin, daemon=True).start()
    else:
        from .voice import VoiceListener
        device = device_arg
        if isinstance(device, str) and device.isdigit():
            device = int(device)
        ptt = None
        if settings["push_to_talk"]:
            from .ptt import ButtonState, PushToTalkGate
            button = ButtonState(settings["push_to_talk"])
            button.start()
            ptt = (PushToTalkGate(tail_seconds=settings["ptt_tail_seconds"]), button.is_held)
            print(f"Push-to-talk on {settings['push_to_talk']}: hold it while you make a call.")
        VoiceListener(model, commands.grammar(data, settings["require_enemy"]),
                      controller.on_text, device, ptt).start()
        first = "'enemy <alias>'" if settings["require_enemy"] else "an alias"
        print(f"Listening. Say {first}, 'cancel <alias>', 'undo', or 'new round'.")

    if not args.window:
        try:
            while True:
                controller.tick()
                time.sleep(0.05)
        except KeyboardInterrupt:
            controller.shutdown()
    else:
        from .ui import StatusWindow
        StatusWindow(controller, settings["window_topmost"]).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
