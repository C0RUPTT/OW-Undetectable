"""Short tones per ability, mixed so overlapping cues don't cut each other off."""
from __future__ import annotations

import queue
import threading

import numpy as np

from .data import AbilityData
from .tracker import Event

RATE = 44100


def tone(freq: float, ms: int, volume: float = 0.25) -> np.ndarray:
    n = int(RATE * ms / 1000)
    t = np.arange(n) / RATE
    wave = np.sin(2 * np.pi * freq * t)
    fade = min(n // 4, int(RATE * 0.008))  # 8ms fades avoid clicks
    env = np.ones(n)
    if fade:
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
    return (wave * env * volume).astype(np.float32)


def silence(ms: int) -> np.ndarray:
    return np.zeros(int(RATE * ms / 1000), dtype=np.float32)


def build_cues(data: AbilityData) -> dict:
    cues = {
        "used": tone(1800, 35, 0.15),
        "unknown": tone(180, 120, 0.2),
        "undone": np.concatenate([tone(900, 50), tone(600, 60)]),
        "cancelled": tone(600, 60),
        "reset": np.concatenate([tone(900, 60), tone(700, 60), tone(500, 80)]),
        "nothing": tone(300, 50, 0.15),
    }
    for a in data.abilities.values():
        cues[("warn", a.id)] = tone(a.tone_hz, 90, 0.18)
        cues[("ready", a.id)] = np.concatenate(
            [tone(a.tone_hz, 70), silence(50), tone(a.tone_hz, 70)]
        )
    return cues


class SoundPlayer:
    def __init__(self, data: AbilityData, enabled: bool = True):
        self.data = data
        self.cues = build_cues(data)
        self._active: list[list] = []  # [buffer, position]
        self._lock = threading.Lock()
        self._stream = None
        self._speech = None
        if enabled:
            import sounddevice as sd

            self._stream = sd.OutputStream(
                samplerate=RATE, channels=1, dtype="float32", callback=self._callback
            )
            self._stream.start()
            if any(a.speak for a in data.abilities.values()):
                self._speech = _Speaker()

    def _callback(self, outdata, frames, _time, _status):
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            for item in self._active:
                buf, pos = item
                chunk = buf[pos:pos + frames]
                out[:len(chunk)] += chunk
                item[1] += frames
            self._active = [i for i in self._active if i[1] < len(i[0])]
        outdata[:, 0] = np.clip(out, -1, 1)

    def _play(self, key) -> None:
        buf = self.cues.get(key)
        if buf is None or self._stream is None:
            return
        with self._lock:
            self._active.append([buf, 0])

    def handle(self, event: Event) -> None:
        if event.kind in ("warn", "ready"):
            ability = self.data.get(event.ability_id)
            if event.kind == "ready" and ability.speak and self._speech:
                self._speech.say(f"{ability.aliases[0]} up")
            else:
                self._play((event.kind, event.ability_id))
        else:
            self._play(event.kind)

    def unknown(self) -> None:
        self._play("unknown")

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()


class _Speaker:
    """pyttsx3 blocks while speaking, so it gets its own thread. Optional dependency."""

    def __init__(self):
        self._q: queue.Queue[str] = queue.Queue()
        try:
            import pyttsx3  # noqa: F401
        except ImportError:
            print("pyttsx3 not installed; spoken cues fall back to tones")
            self._q = None
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 230)
        while True:
            engine.say(self._q.get())
            engine.runAndWait()

    def say(self, text: str) -> None:
        if self._q is not None:
            self._q.put(text)
