"""Offline speech recognition restricted to the command grammar (Vosk)."""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable

SAMPLE_RATE = 16000


def missing_words(model, phrases: list[str]) -> set[str]:
    """Words in the grammar the speech model doesn't know. Vosk silently drops them,
    so an alias made only of missing words can never be heard."""
    words = {w for p in phrases if p != "[unk]" for w in p.split()}
    return {w for w in words if model.vosk_model_find_word(w) < 0}


def unhearable(data, missing: set[str]) -> tuple[list[str], list[str]]:
    """(aliases that can't be heard, ability labels with no hearable alias at all)."""
    dead = [a for a in data.alias_map if missing.intersection(a.split())]
    deaf = [ab.label for ab in data.abilities.values()
            if all(missing.intersection(a.split()) for a in ab.aliases)]
    return sorted(dead), deaf


class VoiceListener:
    def __init__(self, model_path: str, phrases: list[str],
                 on_text: Callable[[str, bool], None], device=None, ptt=None):
        """ptt: optional (PushToTalkGate, is_held) pair. Without it the mic is always on."""
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        self._model = Model(model_path)
        self.missing = missing_words(self._model, phrases)
        self._rec = KaldiRecognizer(self._model, SAMPLE_RATE, json.dumps(phrases))
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
                    self._on_text(json.loads(self._rec.FinalResult()).get("text", ""), True)
                    self._rec.Reset()

    def _recognize(self, data: bytes) -> None:
        if self._rec.AcceptWaveform(data):
            self._on_text(json.loads(self._rec.Result()).get("text", ""), True)
        else:
            self._on_text(json.loads(self._rec.PartialResult()).get("partial", ""), False)
