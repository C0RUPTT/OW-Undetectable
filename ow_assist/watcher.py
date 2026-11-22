"""Notices when the game starts and stops by checking the process list.

Only process names are read. It never opens, reads or touches the game process.
"""
from __future__ import annotations

import threading
import time


class GameWatch:
    """Pure state: turns 'is it running?' samples into start/stop events.
    A grace period means a quick restart or crash doesn't end the session."""

    def __init__(self, grace_seconds: float = 120):
        self.grace = grace_seconds
        self.active = False
        self.last_seen = 0.0

    def update(self, running: bool, now: float) -> str | None:
        if running:
            self.last_seen = now
            if not self.active:
                self.active = True
                return "start"
            return None
        if self.active and now - self.last_seen >= self.grace:
            self.active = False
            return "stop"
        return None


def game_running(process_name: str) -> bool:
    import psutil

    target = process_name.lower()
    for proc in psutil.process_iter(["name"]):
        name = proc.info.get("name")
        if name and name.lower() == target:
            return True
    return False


class GameWatcher:
    def __init__(self, process_name: str, on_start, on_stop, grace_seconds=120, interval=5):
        self.process_name = process_name
        self.on_start, self.on_stop = on_start, on_stop
        self.interval = interval
        self.watch = GameWatch(grace_seconds)

    def start(self) -> bool:
        try:
            import psutil  # noqa: F401
        except ImportError:
            print("psutil not installed: sessions will start on your first logged result")
            return False
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self) -> None:
        while True:
            event = self.watch.update(game_running(self.process_name), time.time())
            if event == "start":
                self.on_start()
            elif event == "stop":
                self.on_stop()
            time.sleep(self.interval)
