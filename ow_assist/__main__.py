"""Entry point: python -m ow_assist --model models/vosk-model-small-en-us-0.15"""
from __future__ import annotations

import argparse
import sys
import threading
import time

from . import commands
from .data import DEFAULT_ABILITIES, DEFAULT_SETTINGS, load_abilities, load_settings
from .sounds import SoundPlayer
from .tracker import Tracker


class Controller:
    def __init__(self, data, settings, sound: SoundPlayer, log=print):
        self.data = data
        self.settings = settings
        self.sound = sound
        self.log = log
        self.tracker = Tracker(data, settings["warn_before_seconds"], settings["call_lag_seconds"])
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
        elif not cmd and text and self.settings["buzz_on_unknown"]:
            self.sound.unknown()

    def _run(self, cmd, text: str) -> None:
        with self._lock:
            events = self.tracker.apply(cmd, time.monotonic())
        self.last_heard = text
        for e in events:
            self.sound.handle(e)
            self.log(f"[{e.kind}] {text}")

    def tick(self):
        with self._lock:
            now = time.monotonic()
            events = self.tracker.poll(now)
            status = self.tracker.status(now)
        for e in events:
            self.sound.handle(e)
            self.log(f"[{e.kind}] {self.data.get(e.ability_id).label}")
        return status, self.last_heard

    def shutdown(self) -> None:
        self.sound.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ow_assist", description="Voice-driven cooldown tracker")
    p.add_argument("--model", help="path to an unzipped Vosk model folder")
    p.add_argument("--text", action="store_true", help="type commands instead of speaking (testing)")
    p.add_argument("--no-ui", action="store_true", help="audio cues only, no window")
    p.add_argument("--no-sound", action="store_true")
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
    controller = Controller(data, settings, SoundPlayer(data, enabled=not args.no_sound))

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
        VoiceListener(args.model, commands.grammar(data), controller.on_text, device).start()
        print("Listening. Say an alias, 'cancel <alias>', 'undo', or 'new round'.")

    if args.no_ui:
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
