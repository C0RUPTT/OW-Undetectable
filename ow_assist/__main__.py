"""Entry point: python -m ow_assist --model models/vosk-model-small-en-us-0.15"""
from __future__ import annotations

import argparse
import sys
import threading
import time

from . import commands
from .data import DEFAULT_ABILITIES, DEFAULT_SETTINGS, load_abilities, load_settings
from .speech import Speaker
from .tracker import Tracker


class Controller:
    def __init__(self, data, settings, speaker: Speaker, log=print):
        self.data = data
        self.settings = settings
        self.speaker = speaker
        self.log = log
        self.tracker = Tracker(data, settings["call_lag_seconds"])
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
        with self._lock:
            events = self.tracker.apply(cmd, time.monotonic())
        self.last_heard = text
        for e in events:
            self.speaker.handle(e)
            self.log(f"[{e.kind}] {text}")

    def tick(self):
        with self._lock:
            now = time.monotonic()
            events = self.tracker.poll(now)
            status = self.tracker.status(now)
        for e in events:
            self.speaker.handle(e)
            self.log(f"[{e.kind}] {self.data.get(e.ability_id).label}")
        return status, self.last_heard

    def ult_snapshot(self) -> dict:
        """Ult timers for the phone view, in data-file order so rows don't jump around."""
        with self._lock:
            status = self.tracker.status(time.monotonic())
        order = {aid: i for i, aid in enumerate(self.data.abilities)}
        ults = sorted(status.ults, key=lambda x: order[x[0].id])
        return {"ults": [{"id": a.id, "hero": a.hero, "name": a.name, "elapsed": round(e, 2)}
                         for a, e in ults]}

    def shutdown(self) -> None:
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
    args = p.parse_args(argv)

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return 0
    if not args.text and not args.model:
        p.error("--model is required unless --text is used")

    data = load_abilities(args.abilities)
    settings = load_settings(args.settings)
    if settings["push_to_talk"]:
        from .ptt import parse_binding
        parse_binding(settings["push_to_talk"])  # fail now, not mid-match
    controller = Controller(data, settings, Speaker(data, enabled=not args.mute, rate=settings["speech_rate"]))

    if args.phone:
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
        device = int(args.device) if args.device and args.device.isdigit() else args.device
        ptt = None
        if settings["push_to_talk"]:
            from .ptt import ButtonState, PushToTalkGate
            button = ButtonState(settings["push_to_talk"])
            button.start()
            ptt = (PushToTalkGate(tail_seconds=settings["ptt_tail_seconds"]), button.is_held)
            print(f"Push-to-talk on {settings['push_to_talk']}: hold it while you make a call.")
        VoiceListener(args.model, commands.grammar(data), controller.on_text, device, ptt).start()
        print("Listening. Say an alias, 'cancel <alias>', 'undo', or 'new round'.")

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
