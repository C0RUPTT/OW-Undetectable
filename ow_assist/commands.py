"""Turn recognized speech into commands."""
from __future__ import annotations

from dataclasses import dataclass

from .data import AbilityData, _normalize

FILLERS = ("enemy ", "their ")
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
           "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
RESULTS = {"gg win": "win", "gg loss": "loss", "gg draw": "draw"}
TILT_KINDS = {"result", "goal", "record"}


@dataclass(frozen=True)
class Command:
    kind: str  # "use", "cancel", "undo", "reset", "result", "goal", "record"
    ability_id: str | None = None
    value: str | int | None = None
    tilted: bool = False


def parse(text: str, data: AbilityData) -> Command | None:
    t = _normalize(text)
    if not t or "[unk]" in t:
        return None
    if t == "undo":
        return Command("undo")
    if t in ("reset", "new round"):
        return Command("reset")
    if t == "record":
        return Command("record")
    if t.endswith(" tilted") and t[: -len(" tilted")] == "gg loss":
        return Command("result", value="loss", tilted=True)
    if t in RESULTS:
        return Command("result", value=RESULTS[t])
    if t == "goal off":
        return Command("goal", value=0)
    if t.startswith("goal ") and t.endswith(" games"):
        n = NUMBERS.get(t[len("goal "):-len(" games")])
        return Command("goal", value=n) if n else None
    kind = "use"
    if t.startswith("cancel "):
        kind, t = "cancel", t[len("cancel "):]
    for filler in FILLERS:
        if t.startswith(filler):
            t = t[len(filler):]
    ability_id = data.alias_map.get(t)
    return Command(kind, ability_id) if ability_id else None


def grammar(data: AbilityData) -> list[str]:
    """Every phrase the recognizer is allowed to hear. Fixed list = fast and accurate."""
    phrases = {"undo", "reset", "new round", "record", "goal off", "gg loss tilted", *RESULTS}
    phrases.update(f"goal {n} games" for n in NUMBERS)
    for alias in data.alias_map:
        phrases.update({alias, f"enemy {alias}", f"cancel {alias}"})
    return sorted(phrases) + ["[unk]"]
