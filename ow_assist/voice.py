"""Offline speech recognition restricted to the command grammar (Vosk)."""
from __future__ import annotations

import json
import queue
import threading
from typing import Callable

SAMPLE_RATE = 16000


class VoiceListener:
    def __init__(self, model_path: str, phrases: list[str],
                 on_text: Callable[[str, bool], None], device=None):
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        self._model = Model(model_path)
        self._rec = KaldiRecognizer(self._model, SAMPLE_RATE, json.dumps(phrases))
        self._on_text = on_text
        self._device = device
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
                if self._rec.AcceptWaveform(data):
                    self._on_text(json.loads(self._rec.Result()).get("text", ""), True)
                else:
                    self._on_text(json.loads(self._rec.PartialResult()).get("partial", ""), False)
