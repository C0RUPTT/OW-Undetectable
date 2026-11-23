"""Mic test: say each call into your headset and see which ones the app mishears.

    python -m ow_assist --mic-test --model models/vosk-model-small-en-us-0.15 --device N
    python -m ow_assist --mic-test gravity nano blade ...   (just these)

It uses the same recognizer, grammar and push-to-talk as a real match. Two results
matter:
- MISSED: nothing usable was heard. Annoying, but the call is just lost.
- WRONG: heard as a *different* call. Worse, because it logs the wrong ult.
         Change one of the two words.
Nothing is recorded; only the recognized text is kept for the report.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import commands
from .data import AbilityData

CORE_COMMANDS = ["won fight", "lost fight", "status", "new round", "undo", "reset",
                 "gravity eighty", "swap nano"]


def default_phrases(data: AbilityData) -> list[str]:
    """Every alias, then the commands you'll say most."""
    order = {aid: i for i, aid in enumerate(data.abilities)}
    aliases = sorted(data.alias_map, key=lambda a: (order[data.alias_map[a]], a))
    extra = [c for c in CORE_COMMANDS if commands.parse(c, data)]
    return aliases + [c for c in extra if c not in aliases]


@dataclass
class Result:
    phrase: str
    heard: list[str] = field(default_factory=list)
    outcome: list[str] = field(default_factory=list)  # "ok", "missed", "wrong"


class MicTest:
    """Pure scoring logic: feed it what was heard for each prompt."""

    def __init__(self, data: AbilityData, phrases: list[str], rounds: int = 1):
        self.data = data
        bad = [p for p in phrases if commands.parse(p, data) is None]
        if bad:
            raise ValueError(f"not commands this app knows: {bad}")
        self.results = [Result(p) for p in phrases]
        self.rounds = rounds
        self._queue = [r for _ in range(rounds) for r in self.results]
        self._pos = 0

    @property
    def total(self) -> int:
        return len(self._queue)

    @property
    def done(self) -> int:
        return self._pos

    def next_prompt(self) -> str | None:
        return self._queue[self._pos].phrase if self._pos < len(self._queue) else None

    def record(self, heard: str) -> str:
        r = self._queue[self._pos]
        self._pos += 1
        heard = " ".join(heard.lower().split())
        want = commands.parse(r.phrase, self.data)
        got = commands.parse(heard, self.data) if heard else None
        outcome = "ok" if got == want else ("missed" if got is None else "wrong")
        r.heard.append(heard or "(nothing)")
        r.outcome.append(outcome)
        return outcome

    def report(self) -> str:
        tried = [r for r in self.results if r.outcome]
        if not tried:
            return "No calls tested."
        attempts = sum(len(r.outcome) for r in tried)
        ok = sum(o == "ok" for r in tried for o in r.outcome)
        wrong = [r for r in tried if "wrong" in r.outcome]
        missed = [r for r in tried if "missed" in r.outcome and "wrong" not in r.outcome]
        lines = [f"{ok}/{attempts} heard correctly ({ok / attempts:.0%})."]
        if wrong:
            lines.append("\nWRONG: heard as a different call. Change one of the two words:")
            for r in wrong:
                lines.append(f"  {r.phrase!r:20} heard as: "
                             + ", ".join(h for h, o in zip(r.heard, r.outcome) if o == "wrong"))
        if missed:
            lines.append("\nMISSED: nothing usable heard. Try again, or pick a longer word:")
            for r in missed:
                lines.append(f"  {r.phrase!r:20} heard: "
                             + ", ".join(h for h, o in zip(r.heard, r.outcome) if o == "missed"))
        if not wrong and not missed:
            lines.append("Every call was heard right.")
        else:
            lines.append("\nChange words in data/abilities.json ('aliases'), then rerun with "
                         "just those words: python -m ow_assist --mic-test word1 word2 ...")
        return "\n".join(lines)


def run(test: MicTest, listen, out=print, pause: float = 0.6) -> str:
    """listen(timeout) -> recognized text ('' if nothing). Returns the report."""
    out(f"Mic test: {test.total} calls. Say each one the way you would in a match.")
    out("Press Ctrl+C to stop early and still get the report.\n")
    try:
        while (phrase := test.next_prompt()) is not None:
            out(f"[{test.done + 1}/{test.total}]  Say:  {phrase.upper()}")
            heard = listen(8.0)
            outcome = test.record(heard)
            mark = {"ok": "ok", "missed": "MISSED", "wrong": "WRONG"}[outcome]
            out(f"        heard: {heard or '(nothing)'}  -> {mark}")
            time.sleep(pause)
    except KeyboardInterrupt:
        out("\nStopped early.")
    return test.report()
