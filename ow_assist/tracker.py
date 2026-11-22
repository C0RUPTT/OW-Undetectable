"""Pure timer logic. Time is passed in, so it is fully testable."""
from __future__ import annotations

from dataclasses import dataclass

from .commands import Command
from .data import Ability, AbilityData

MAX_UNDO = 30


@dataclass(frozen=True)
class Event:
    kind: str  # "used", "ready", "cancelled", "undone", "reset", "nothing"
    ability_id: str | None = None


@dataclass(frozen=True)
class Status:
    cooldowns: list[tuple[Ability, float]]  # (ability, seconds remaining)
    ults: list[tuple[Ability, float]]       # (ability, seconds since used)


class Tracker:
    def __init__(self, data: AbilityData, call_lag: float = 0.0):
        self.data = data
        self.call_lag = call_lag
        self._ready_at: dict[str, float] = {}
        self._ult_used_at: dict[str, float] = {}
        self._history: list[tuple[dict, dict]] = []

    def _snapshot(self) -> None:
        self._history.append((dict(self._ready_at), dict(self._ult_used_at)))
        del self._history[:-MAX_UNDO]

    def apply(self, cmd: Command, now: float) -> list[Event]:
        if cmd.kind == "undo":
            if not self._history:
                return [Event("nothing")]
            self._ready_at, self._ult_used_at = self._history.pop()
            return [Event("undone")]

        if cmd.kind == "reset":
            self._snapshot()
            self._ready_at.clear()
            self._ult_used_at.clear()
            return [Event("reset")]

        ability = self.data.get(cmd.ability_id)

        if cmd.kind == "cancel":
            if ability.id not in self._ready_at and ability.id not in self._ult_used_at:
                return [Event("nothing", ability.id)]
            self._snapshot()
            self._ready_at.pop(ability.id, None)
            self._ult_used_at.pop(ability.id, None)
            return [Event("cancelled", ability.id)]

        self._snapshot()
        used_at = now - self.call_lag
        if ability.kind == "ult":
            self._ult_used_at[ability.id] = used_at
        else:
            self._ready_at[ability.id] = used_at + ability.recharge_seconds
        return [Event("used", ability.id)]

    def poll(self, now: float) -> list[Event]:
        ready = sorted((r, a) for a, r in self._ready_at.items() if now >= r)
        for _, aid in ready:
            del self._ready_at[aid]
        return [Event("ready", aid) for _, aid in ready]

    def status(self, now: float) -> Status:
        cds = sorted(
            ((self.data.get(a), max(0.0, r - now)) for a, r in self._ready_at.items()),
            key=lambda x: x[1],
        )
        ults = sorted(
            ((self.data.get(a), now - t) for a, t in self._ult_used_at.items()),
            key=lambda x: x[1],
        )
        return Status(cds, ults)
