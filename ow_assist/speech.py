"""Spoken callouts. Text-to-speech blocks while talking, so it runs on its own thread."""
from __future__ import annotations

import queue
import threading

from .data import AbilityData
from .tracker import Event

CORRECTIONS = {"undone": "undone", "cancelled": "cleared", "reset": "cleared"}


def phrase_for(event: Event, data: AbilityData) -> str | None:
    """What to say for an event, or None to stay silent."""
    if event.kind == "ready":
        return data.get(event.ability_id).callout
    return CORRECTIONS.get(event.kind)


class Speaker:
    def __init__(self, data: AbilityData, enabled: bool = True, rate: int = 230):
        self.data = data
        self._q: queue.Queue[str] | None = None
        if enabled:
            import pyttsx3  # noqa: F401  (fail at startup, not mid-match)

            self._q = queue.Queue()
            threading.Thread(target=self._run, args=(rate,), daemon=True).start()

    def _run(self, rate: int) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        while True:
            engine.say(self._q.get())
            engine.runAndWait()

    def handle(self, event: Event) -> None:
        text = phrase_for(event, self.data)
        if text:
            self.say(text)

    def say(self, text: str) -> None:
        if self._q is not None:
            self._q.put(text)

    def close(self) -> None:
        pass
