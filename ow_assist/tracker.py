"""Pure timer logic. Time is passed in, so it is fully testable."""
from __future__ import annotations

from dataclasses import dataclass

from .commands import Command
from .data import Ability, AbilityData

MAX_UNDO = 30


@dataclass(frozen=True)
class Event:
    kind: str  # "used", "warn", "ready", "cancelled", "undone", "reset", "nothing"
    ability_id: str | None = None


@dataclass(frozen=True)
class Status:
    cooldowns: list[tuple[Ability, float]]  # (ability, seconds remaining)
    ults: list[tuple[Ability, float]]       # (ability, seconds since used)


class Tracker:
    def __init__(self, data: AbilityData, warn_before: float = 3.0, call_lag: float = 0.0):
        self.data = data
        self.warn_before = warn_before
        self.call_lag = call_lag
        self._ready_at: dict[str, float] = {}
        self._warned: set[str] = set()
        self._ult_used_at: dict[str, float] = {}
        self._history: list[tuple] = []

    def _snapshot(self) -> None:
        self._history.append((dict(self._ready_at), set(self._warned), dict(self._ult_used_at)))
        del self._history[:-MAX_UNDO]

    def apply(self, cmd: Command, now: float) -> list[Event]:
        if cmd.kind == "undo":
            if not self._history:
                return [Event("nothing")]
            self._ready_at, self._warned, self._ult_used_at = self._history.pop()
            return [Event("undone")]

        if cmd.kind == "reset":
            self._snapshot()
            self._ready_at.clear()
            self._warned.clear()
            self._ult_used_at.clear()
            return [Event("reset")]

        ability = self.data.get(cmd.ability_id)
        used_at = now - self.call_lag

        if cmd.kind == "cancel":
            if ability.id not in self._ready_at and ability.id not in self._ult_used_at:
                return [Event("nothing", ability.id)]
            self._snapshot()
            self._ready_at.pop(ability.id, None)
            self._warned.discard(ability.id)
            self._ult_used_at.pop(ability.id, None)
            return [Event("cancelled", ability.id)]

        self._snapshot()
        if ability.kind == "ult":
            self._ult_used_at[ability.id] = used_at
        else:
            self._ready_at[ability.id] = used_at + ability.recharge_seconds
            self._warned.discard(ability.id)
            if self._ready_at[ability.id] - now <= self.warn_before:
                self._warned.add(ability.id)  # too short to bother warning
        return [Event("used", ability.id)]

    def poll(self, now: float) -> list[Event]:
        events = []
        for aid, ready_at in sorted(self._ready_at.items(), key=lambda kv: kv[1]):
            if now >= ready_at:
                events.append(Event("ready", aid))
            elif aid not in self._warned and ready_at - now <= self.warn_before:
                self._warned.add(aid)
                events.append(Event("warn", aid))
        for e in events:
            if e.kind == "ready":
                del self._ready_at[e.ability_id]
                self._warned.discard(e.ability_id)
        return events

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
