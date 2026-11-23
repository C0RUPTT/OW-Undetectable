"""Entry point: python -m ow_assist --model models/vosk-model-small-en-us-0.15"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time

from . import commands
from .data import (DEFAULT_ABILITIES, DEFAULT_HISTORY, DEFAULT_RATES, DEFAULT_SETTINGS,
                   DEFAULT_SETTING_VALUES, load_abilities, load_settings)
from .speech import Speaker
from .tracker import Tracker


UNDOABLE = ("used", "cancelled", "reset", "round", "swapped", "fight")


def load_rates(path) -> list[float]:
    """Charge rates learned from earlier games (see estimate.py)."""
    try:
        return [float(x) for x in json.loads(open(path, encoding="utf-8").read())["samples"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def save_rates(path, samples: list[float]) -> None:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"samples": [round(x, 2) for x in samples]}), encoding="utf-8")


class Controller:
    def __init__(self, data, settings, speaker: Speaker, tilt=None, log=print, rates_path=None):
        self.data = data
        self.tilt = tilt
        self._undo_owners: list[str] = []  # who handled each undoable action, newest last
        self.settings = settings = {**DEFAULT_SETTING_VALUES, **settings}
        self.speaker = speaker
        self.log = log
        self.rates_path = rates_path
        self.tracker = Tracker(
            data, settings["call_lag_seconds"],
            possible_rate=settings["ult_possible_rate"],
            likely_rate=settings["ult_likely_rate"],
            learn_rates=settings["ult_learn_rates"],
            swap_kept=settings["ult_swap_kept_fraction"],
            repeat_ignore=settings["ult_repeat_ignore_seconds"],
            callout_tiers=tuple(settings["ult_callout_tiers"]),
            samples=load_rates(rates_path) if rates_path else None,
        )
        self._saved_samples = list(self.tracker.samples)
        self._lock = threading.Lock()
        self._fired_partial: str | None = None
        self.last_heard = ""

    def on_text(self, text: str, final: bool) -> None:
        """Called from the voice thread with partial and final recognition results."""
        cmd = commands.parse(text, self.data)
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
                if events[0].kind in UNDOABLE:
                    self._undo_owners.append("tracker")
                lines = []
            self._save_rates()
        self._say(lines)
        for e in events:
            self.speaker.handle(e)
            self.log(f"[{e.kind}] {text}" + (f" -> {e.say}" if e.say else ""))

    def _save_rates(self) -> None:
        """Keep learned charge rates for next time. Call with the lock held."""
        if self.rates_path and self.tracker.samples != self._saved_samples:
            self._saved_samples = list(self.tracker.samples)
            try:
                save_rates(self.rates_path, self._saved_samples)
            except OSError as e:
                self.log(f"[warn] couldn't save ult rates: {e}")

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
            self.log(f"[{e.kind}] {e.say or self.data.get(e.ability_id).label}")
        self._say(lines)
        return status, self.last_heard

    def ult_snapshot(self) -> dict:
        """Ult timers for the phone view, in data-file order so rows don't jump around."""
        with self._lock:
            now = time.monotonic()
            status = self.tracker.status(now)
            fights = self.tracker.fights
            in_fight = len(self.tracker.fight_uses)
            rates = self.tracker.rates()
            samples = len(self.tracker.samples)
            session = self.tilt.snapshot(time.time()) if self.tilt else None
        order = {aid: i for i, aid in enumerate(self.data.abilities)}
        ults = sorted(status.ults, key=lambda u: order[u.ability.id])
        return {"ults": [{"id": u.ability.id, "hero": u.ability.hero, "name": u.ability.name,
                          "alias": u.ability.aliases[0], "tier": u.ability.tier,
                          "elapsed": round(u.elapsed, 2), "anchor": u.anchor, "state": u.state,
                          "possible_in": round(u.possible_in, 1),
                          "likely_in": round(u.likely_in, 1), "charge": round(u.charge, 3)}
                         for u in ults],
                "fights": [{"result": r, "used": n} for r, n in fights[-8:]],
                "in_fight": in_fight,
                "rates": {"possible": round(rates.possible, 1), "likely": round(rates.likely, 1),
                          "samples": samples},
                "session": session}

    def shutdown(self) -> None:
        with self._lock:
            self._save_rates()
        if self.tilt:
            with self._lock:
                self.tilt.end_session(time.time())
        self.speaker.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ow_assist", description="Voice-driven cooldown tracker")
    p.add_argument("--model", help="path to an unzipped Vosk model folder")
    p.add_argument("--text", action="store_true", help="type commands instead of speaking (testing)")
    p.add_argument("--window", action="store_true", help="also show the status window (ult timers)")
    p.add_argument("--phone", action="store_true", help="serve the ult view to your phone")
    p.add_argument("--mute", action="store_true", help="no speech (testing)")
    p.add_argument("--device", help="microphone device name or index (see --list-devices)")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--abilities", default=str(DEFAULT_ABILITIES))
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    p.add_argument("--history", default=str(DEFAULT_HISTORY), help="where game results are stored")
    p.add_argument("--rates", default=str(DEFAULT_RATES),
                   help="where learned ult charge rates are stored")
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
    if not args.text and not args.model:
        p.error("--model is required unless --text is used")

    data = load_abilities(args.abilities)
    settings = load_settings(args.settings)
    if settings["push_to_talk"]:
        from .ptt import parse_binding
        parse_binding(settings["push_to_talk"])  # fail now, not mid-match
    from .tilt import Store, TiltTracker
    tilt = TiltTracker(Store(args.history), settings["warn_after_losses"],
                       settings["stop_after_losses"], settings["long_session_minutes"],
                       settings["session_gap_minutes"])
    speaker = Speaker(data, enabled=not args.mute, rate=settings["speech_rate"])
    controller = Controller(data, settings, speaker, tilt, rates_path=args.rates)

    from .watcher import GameWatcher
    GameWatcher(settings["game_process"], controller.game_started, controller.game_stopped,
                settings["session_end_grace_seconds"]).start()

    if args.phone:
        from .phone import PhoneServer
        phone = PhoneServer(controller.ult_snapshot, port=settings["phone_port"])
        phone.start()
        print(f"Phone view: open {phone.url} on your phone (same Wi-Fi)")

    if args.text:
        def read_stdin():
            print("Type commands (e.g. 'grav', 'won fight', 'status', 'swap grav', 'undo'):")
            for line in sys.stdin:
                if not commands.parse(line, data):
                    print("  not a command")
                controller.on_text(line.strip(), True)
        threading.Thread(target=read_stdin, daemon=True).start()
    else:
        from .voice import VoiceListener
        device = int(args.device) if args.device and args.device.isdigit() else args.device
        ptt = None
        if settings["push_to_talk"]:
            from .ptt import ButtonState, PushToTalkGate
            button = ButtonState(settings["push_to_talk"])
            button.start()
            ptt = (PushToTalkGate(tail_seconds=settings["ptt_tail_seconds"]), button.is_held)
            print(f"Push-to-talk on {settings['push_to_talk']}: hold it while you make a call.")
        listener = VoiceListener(args.model, commands.grammar(data), controller.on_text, device, ptt)
        if listener.missing:
            from .voice import unhearable
            dead, deaf = unhearable(data, listener.missing)
            print(f"Warning: the speech model doesn't know {sorted(listener.missing)}.")
            print(f"  These calls can't be heard: {dead}")
            if deaf:
                print(f"  No working alias at all for: {deaf}. Add a plain-English alias "
                      "for them in data/abilities.json.")
        listener.start()
        print("Listening. Say an ult or ability, 'won fight' / 'lost fight', 'status', "
              "'swap <ult>', 'undo', or 'new round'.")

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
