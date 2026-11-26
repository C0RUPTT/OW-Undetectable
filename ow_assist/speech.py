"""Spoken callouts. Text-to-speech blocks while talking, so it runs on its own thread."""
from __future__ import annotations

import queue
import sys
import threading

from .data import AbilityData
from .tracker import Event

CORRECTIONS = {"undone": "undone", "cancelled": "cleared", "reset": "cleared"}


def phrase_for(event: Event, data: AbilityData) -> str | None:
    """What to say for an event, or None to stay silent."""
    if event.kind == "ready":
        return data.get(event.ability_id).callout
    return CORRECTIONS.get(event.kind)


def sapi_rate(words_per_minute: int) -> int:
    """Windows SAPI takes a rate from -10 to 10 (0 is about 180 words a minute)."""
    return max(-10, min(10, round((words_per_minute - 180) / 20)))


class Speaker:
    def __init__(self, data: AbilityData, enabled: bool = True, rate: int = 230, log=print):
        self.data = data
        self.log = log
        self._q: queue.Queue[str] | None = None
        if enabled:
            self._q = queue.Queue()
            say = self._make_voice(rate)  # fail at startup, not mid-match
            threading.Thread(target=self._run, args=(say,), daemon=True).start()

    def _make_voice(self, rate: int):
        """Return a function that speaks one line and waits until it's done.

        On Windows this talks to SAPI directly: pyttsx3 there often goes silent after
        the first line when it's reused on a background thread.
        """
        if sys.platform == "win32":
            try:
                import win32com.client  # noqa: F401  (comes with pyttsx3 on Windows)

                def say_sapi(text, _voice=[]):
                    if not _voice:  # COM objects must be created on the thread that uses them
                        import pythoncom
                        import win32com.client
                        pythoncom.CoInitialize()
                        v = win32com.client.Dispatch("SAPI.SpVoice")
                        v.Rate = sapi_rate(rate)
                        _voice.append(v)
                    _voice[0].Speak(text)
                return say_sapi
            except ImportError:
                pass
        import pyttsx3

        def say_pyttsx3(text):
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.say(text)
            engine.runAndWait()
        return say_pyttsx3

    def _run(self, say) -> None:
        while True:
            text = self._q.get()
            try:
                say(text)
            except Exception as e:  # one failed line must not silence the rest of the match
                self.log(f"[speech error] {e!r}")

    def handle(self, event: Event) -> None:
        text = phrase_for(event, self.data)
        if text:
            self.say(text)

    def say(self, text: str) -> None:
        if self._q is not None:
            self._q.put(text)

    def close(self) -> None:
        pass
