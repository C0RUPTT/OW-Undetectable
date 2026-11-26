"""Offline speech recognition restricted to the command grammar (Vosk)."""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable

SAMPLE_RATE = 16000


def known_phrases(phrases: list[str], find_word) -> tuple[list[str], list[str]]:
    """Split phrases into ones the model's vocabulary covers and bare words it lacks.

    find_word returns -1 for a word the model doesn't know. "[unk]" is always kept.
    """
    kept, dropped = [], set()
    for phrase in phrases:
        missing = [w for w in phrase.split() if phrase != "[unk]" and find_word(w) < 0]
        if missing:
            dropped.update(missing)
        else:
            kept.append(phrase)
    return kept, sorted(dropped)


class VoiceListener:
    def __init__(self, model_path: str, phrases: list[str],
                 on_text: Callable[..., None], device=None, ptt=None):
        """ptt: optional (PushToTalkGate, is_held) pair. Without it the mic is always on."""
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        self._model = Model(model_path)
        phrases, dropped = known_phrases(phrases, self._model.vosk_model_find_word)
        if dropped:
            print("The speech model can't hear these, use another alias: " + ", ".join(dropped))
        self._rec = KaldiRecognizer(self._model, SAMPLE_RATE, json.dumps(phrases))
        self._rec.SetWords(True)  # per-word confidence, used to skip unsure matches
        self._on_text = on_text
        self._device = device
        self._ptt = ptt
        self._audio: queue.Queue[bytes] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import sounddevice as sd

        def callback(indata, _frames, _time, _status):
            self._audio.put(bytes(indata))

        # 100ms blocks keep latency low. Audio is processed in memory and never saved.
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=1600, dtype="int16",
                               channels=1, callback=callback, device=self._device):
            while not self._stop.is_set():
                try:
                    data = self._audio.get(timeout=0.2)
                except queue.Empty:
                    continue
                if self._ptt is None:
                    self._recognize(data)
                    continue
                gate, is_held = self._ptt
                blocks, finalize = gate.feed(data, is_held(), time.monotonic())
                for block in blocks:
                    self._recognize(block)
                if finalize:
                    self._final(self._rec.FinalResult())
                    self._rec.Reset()

    def _recognize(self, data: bytes) -> None:
        if self._rec.AcceptWaveform(data):
            self._final(self._rec.Result())
        else:
            self._on_text(json.loads(self._rec.PartialResult()).get("partial", ""), False)

    def _final(self, raw: str) -> None:
        result = json.loads(raw)
        self._on_text(result.get("text", ""), True, confidence(result))


def confidence(result: dict) -> float | None:
    """Lowest word confidence in a final result (0..1), or None if Vosk gave none."""
    words = result.get("result") or []
    return min(w["conf"] for w in words) if words else None
