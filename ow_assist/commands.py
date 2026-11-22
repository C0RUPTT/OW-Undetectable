"""Turn recognized speech into tracker commands."""
from __future__ import annotations

from dataclasses import dataclass

from .data import AbilityData, _normalize

FILLERS = ("enemy ", "their ")


@dataclass(frozen=True)
class Command:
    kind: str  # "use", "cancel", "undo", "reset"
    ability_id: str | None = None


def parse(text: str, data: AbilityData) -> Command | None:
    t = _normalize(text)
    if not t or "[unk]" in t:
        return None
    if t == "undo":
        return Command("undo")
    if t in ("reset", "new round"):
        return Command("reset")
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
    phrases = {"undo", "reset", "new round"}
    for alias in data.alias_map:
        phrases.update({alias, f"enemy {alias}", f"cancel {alias}"})
    return sorted(phrases) + ["[unk]"]
