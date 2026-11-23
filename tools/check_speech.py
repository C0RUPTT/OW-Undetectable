"""Check how well the speech model hears every call, before you rely on it in a match.

    python tools/check_speech.py models/vosk-model-small-en-us-0.15

It speaks every alias and command with a synthetic voice (espeak-ng), at a few speeds
and accents, with and without background noise. Each clip goes through the same
recognizer and grammar the app uses, then the result is checked against the command
it should have triggered. Misheard words are listed with what was heard instead.

Needs: espeak-ng on PATH (Windows installer: github.com/espeak-ng/espeak-ng/releases),
plus `pip install numpy vosk`. A synthetic voice isn't yours, so treat a word that fails
here as a word to replace, and a word that passes as "probably fine".
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from vosk import KaldiRecognizer, Model, SetLogLevel  # noqa: E402

from ow_assist import commands  # noqa: E402
from ow_assist.data import load_abilities  # noqa: E402

RATE = 16000
# (voice, words per minute, noise SNR in dB or None)
CONDITIONS = [("en-us", 160, None), ("en-us", 220, None), ("en-gb", 180, None),
              ("en-us", 190, 15), ("en-gb", 200, 10), ("en-us", 140, 10)]
EXTRA = ["won fight", "lost fight", "status", "new round", "undo", "reset"]


def synth(text: str, voice: str, speed: int) -> np.ndarray:
    out = subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "--stdout", text],
                         capture_output=True, check=True).stdout
    with wave.open(io.BytesIO(out)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    y = np.interp(np.linspace(0, len(x) - 1, int(len(x) * RATE / sr)), np.arange(len(x)), x)
    pad = np.zeros(RATE // 4, dtype=np.float32)
    return np.concatenate([pad, y, pad, pad])


def recognize(model: Model, grammar: str, audio: np.ndarray) -> str:
    rec = KaldiRecognizer(model, RATE, grammar)
    pcm = np.clip(audio, -32768, 32767).astype(np.int16).tobytes()
    for i in range(0, len(pcm), 3200):
        rec.AcceptWaveform(pcm[i:i + 3200])
    return json.loads(rec.FinalResult()).get("text", "")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    SetLogLevel(-1)
    model = Model(argv[1])
    data = load_abilities(argv[2]) if len(argv) > 2 else load_abilities()
    phrases = commands.grammar(data)
    missing = sorted({w for p in phrases if p != "[unk]" for w in p.split()
                      if model.vosk_model_find_word(w) < 0})
    if missing:
        print(f"Not in the model's vocabulary (can never be heard): {missing}\n")
    grammar = json.dumps(phrases)
    rng = np.random.default_rng(0)
    tests = sorted(set(data.alias_map) | set(EXTRA))
    ok = total = 0
    fails: dict[str, list[str]] = {}
    for phrase in tests:
        want = commands.parse(phrase, data)
        for voice, speed, snr in CONDITIONS:
            audio = synth(phrase, voice, speed)
            if snr is not None:
                power = float(np.mean(audio ** 2))
                audio = audio + rng.normal(0, np.sqrt(power / 10 ** (snr / 10)), len(audio))
            heard = recognize(model, grammar, audio)
            total += 1
            if commands.parse(heard, data) == want:
                ok += 1
            else:
                tag = f"{voice}/{speed}" + (f"/noise{snr}" if snr else "")
                fails.setdefault(phrase, []).append(f"{tag} heard '{heard}'")
    print(f"{ok}/{total} correct ({ok / total:.1%}): {len(tests)} phrases x "
          f"{len(CONDITIONS)} conditions")
    for phrase, why in sorted(fails.items(), key=lambda kv: -len(kv[1])):
        print(f"  {phrase!r:20} {len(why)}/{len(CONDITIONS)} wrong: " + "; ".join(why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
