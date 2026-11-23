"""Pure timer logic. Time is passed in, so it is fully testable."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from . import estimate
from .commands import Command
from .data import Ability, AbilityData

MAX_UNDO = 30
TIER_ORDER = {"engage": 0, "kill": 1, "save": 2, "minor": 3}
STATE_ORDER = {"likely": 0, "possible": 1, "charging": 2, "used": 3, "unknown": 4}
GROUP_CALLOUT_SECONDS = 10.0  # ults due this close together are announced in one line


@dataclass(frozen=True)
class Event:
    # "used", "ready", "cancelled", "undone", "reset", "round", "swapped", "seen", "fight",
    # "status", "ult_possible", "nothing"
    kind: str
    ability_id: str | None = None
    say: str | None = None


@dataclass(frozen=True)
class UltStatus:
    ability: Ability
    elapsed: float       # seconds since the anchor (use, swap or round start)
    anchor: str          # "used", "swap", "seen" (kill cam) or "round"
    state: str           # see estimate.STATES
    possible_in: float   # seconds until possible (0 once it is)
    likely_in: float     # seconds until likely (0 once it is)
    charge: float        # 0..1 estimate at the typical rate
    possible_after: float = 0.0  # seconds after the anchor it becomes possible (0 = unknown)
    likely_after: float = 0.0


@dataclass(frozen=True)
class Status:
    cooldowns: list[tuple[Ability, float]]  # (ability, seconds remaining)
    ults: list[UltStatus]


@dataclass
class _Anchor:
    at: float
    kind: str              # "used", "swap", "seen", "round"
    start_points: float = 0.0
    announced: bool = False


@dataclass
class _State:
    ready_at: dict[str, float] = field(default_factory=dict)
    ults: dict[str, _Anchor] = field(default_factory=dict)
    fight_uses: list[str] = field(default_factory=list)   # enemy ults since the last fight ended
    fights: list[tuple[str, int]] = field(default_factory=list)  # (won/lost, ults they used)
    samples: list[float] = field(default_factory=list)    # observed charge rates, points/s


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


class Tracker:
    def __init__(self, data: AbilityData, call_lag: float = 0.0, *,
                 possible_rate: float = estimate.DEFAULT_POSSIBLE_RATE,
                 likely_rate: float = estimate.DEFAULT_LIKELY_RATE,
                 learn_rates: bool = True, swap_kept: float = 0.15,
                 repeat_ignore: float = 8.0,
                 callout_tiers: tuple[str, ...] = ("engage", "kill"),
                 samples: list[float] | None = None):
        self.data = data
        self.call_lag = call_lag
        self.possible_rate = possible_rate
        self.likely_rate = likely_rate
        self.learn_rates = learn_rates
        self.swap_kept = swap_kept
        self.repeat_ignore = repeat_ignore
        self.callout_tiers = tuple(callout_tiers)
        self.s = _State(samples=list(samples or [])[-estimate.MAX_SAMPLES:])
        self._history: list[_State] = []

    # --- rates -----------------------------------------------------------------
    @property
    def samples(self) -> list[float]:
        return self.s.samples

    def rates(self) -> estimate.Rates:
        if not self.learn_rates:
            return estimate.Rates(self.possible_rate, self.likely_rate)
        return estimate.calibrated(self.s.samples, self.possible_rate, self.likely_rate)

    def _window(self, ability: Ability, anchor: _Anchor) -> tuple[float, float] | None:
        if not ability.cost:
            return None
        return estimate.window(ability.cost, anchor.start_points, self.rates())

    # --- commands --------------------------------------------------------------
    def _snapshot(self) -> None:
        self._history.append(copy.deepcopy(self.s))
        del self._history[:-MAX_UNDO]

    def apply(self, cmd: Command, now: float) -> list[Event]:
        s = self.s
        if cmd.kind == "undo":
            if not self._history:
                return [Event("nothing")]
            self.s = self._history.pop()
            return [Event("undone")]

        if cmd.kind == "status":
            return [Event("status", say=self.status_line(now))]

        if cmd.kind == "reset":
            self._snapshot()
            s.ready_at.clear()
            s.ults.clear()
            s.fight_uses.clear()
            s.fights.clear()
            return [Event("reset")]

        if cmd.kind == "round":
            # Ult charge goes back to 0 for everyone; the enemy comp usually stays.
            self._snapshot()
            s.ready_at.clear()
            s.ults = {aid: _Anchor(now, "round") for aid in s.ults}
            s.fight_uses.clear()
            s.fights.clear()
            return [Event("round")]

        if cmd.kind == "fight":
            self._snapshot()
            used = list(s.fight_uses)
            s.fights.append((cmd.value, len(used)))
            s.fight_uses.clear()
            return [Event("fight", say=self.fight_summary(used, now))]

        ability = self.data.get(cmd.ability_id)

        if cmd.kind == "cancel":
            if ability.id not in s.ready_at and ability.id not in s.ults:
                return [Event("nothing", ability.id)]
            self._snapshot()
            s.ready_at.pop(ability.id, None)
            s.ults.pop(ability.id, None)
            if ability.id in s.fight_uses:
                s.fight_uses.remove(ability.id)
            return [Event("cancelled", ability.id)]

        if cmd.kind == "swap":
            # They just switched to this hero: at most 15% of the ult is kept.
            if ability.kind != "ult":
                if ability.id not in s.ready_at:
                    return [Event("nothing", ability.id)]
                self._snapshot()
                s.ready_at.pop(ability.id)  # a fresh hero has every cooldown ready
                return [Event("swapped", ability.id)]
            self._snapshot()
            s.ults[ability.id] = _Anchor(now - self.call_lag, "swap",
                                         start_points=self.swap_kept * ability.cost)
            return [Event("swapped", ability.id)]

        if cmd.kind == "seen":
            # The kill cam showed their real charge: the best data point there is.
            if ability.kind != "ult":
                return [Event("nothing", ability.id)]
            self._snapshot()
            pct = min(100, int(cmd.value)) / 100.0
            prev = s.ults.get(ability.id)
            if prev and self.learn_rates and ability.cost and pct >= 0.3:
                win = self._window(ability, prev)
                rate = estimate.observed_rate(pct * ability.cost, prev.start_points,
                                              now - prev.at, win[1])
                if rate is not None:
                    s.samples.append(rate)
                    del s.samples[:-estimate.MAX_SAMPLES]
            s.ults[ability.id] = _Anchor(now, "seen", start_points=pct * ability.cost,
                                         announced=pct >= 1.0)
            return [Event("seen", ability.id)]

        used_at = now - self.call_lag
        if ability.kind != "ult":
            self._snapshot()
            s.ready_at[ability.id] = used_at + ability.recharge_seconds
            return [Event("used", ability.id)]

        prev = s.ults.get(ability.id)
        if prev and prev.kind == "used" and used_at - prev.at < self.repeat_ignore:
            return [Event("nothing", ability.id)]  # same ult called twice
        self._snapshot()
        if prev and self.learn_rates and ability.cost:
            win = self._window(ability, prev)
            rate = estimate.observed_rate(ability.cost, prev.start_points,
                                          used_at - prev.at, win[1])
            if rate is not None:
                s.samples.append(rate)
                del s.samples[:-estimate.MAX_SAMPLES]
        s.ults[ability.id] = _Anchor(used_at, "used")
        s.fight_uses.append(ability.id)
        return [Event("used", ability.id)]

    # --- time passing ------------------------------------------------------------
    def poll(self, now: float) -> list[Event]:
        s = self.s
        ready = sorted((r, a) for a, r in s.ready_at.items() if now >= r)
        for _, aid in ready:
            del s.ready_at[aid]
        events = [Event("ready", aid) for _, aid in ready]

        due, soon = [], []
        for aid, anchor in s.ults.items():
            ability = self.data.get(aid)
            if anchor.announced or ability.tier not in self.callout_tiers:
                continue
            win = self._window(ability, anchor)
            if win is None:
                continue
            left = win[0] - (now - anchor.at)
            if left <= 0:
                due.append(aid)
            elif left <= GROUP_CALLOUT_SECONDS:
                soon.append(aid)
        if due:
            group = due + soon
            for aid in group:
                s.ults[aid].announced = True
            names = [self.data.get(a).aliases[0] for a in self._ordered(group)]
            events.append(Event("ult_possible", group[0], say=f"{_join(names)} may be up"))
        return events

    # --- reading state -----------------------------------------------------------
    def _ordered(self, ids: list[str]) -> list[str]:
        order = {aid: i for i, aid in enumerate(self.data.abilities)}
        return sorted(ids, key=lambda a: (TIER_ORDER.get(self.data.get(a).tier, 9), order[a]))

    def ult_status(self, aid: str, now: float) -> UltStatus:
        ability, anchor = self.data.get(aid), self.s.ults[aid]
        elapsed = now - anchor.at
        win = self._window(ability, anchor)
        if win is None:
            st = "used" if anchor.kind == "used" and elapsed < 15 else "unknown"
            return UltStatus(ability, elapsed, anchor.kind, st, 0.0, 0.0, 0.0)
        possible_after, likely_after = win
        charge = 1.0
        if ability.cost:
            charge = min(1.0, (anchor.start_points + elapsed * self.rates().likely) / ability.cost)
        return UltStatus(
            ability, elapsed, anchor.kind,
            estimate.state(elapsed, anchor.kind, possible_after, likely_after),
            max(0.0, possible_after - elapsed), max(0.0, likely_after - elapsed), charge,
            possible_after, likely_after,
        )

    def peek(self, aid: str | None, now: float) -> UltStatus | None:
        """The estimate for one ult right now, or None if it isn't tracked."""
        return self.ult_status(aid, now) if aid in self.s.ults else None

    def status(self, now: float) -> Status:
        cds = sorted(
            ((self.data.get(a), max(0.0, r - now)) for a, r in self.s.ready_at.items()),
            key=lambda x: x[1],
        )
        ults = sorted((self.ult_status(a, now) for a in self.s.ults), key=lambda u: u.elapsed)
        return Status(cds, ults)

    def threats(self, now: float, exclude: tuple[str, ...] = ()) -> list[UltStatus]:
        """Ults that may be up, most dangerous first: likely before possible, then by tier."""
        ups = [u for u in (self.ult_status(a, now) for a in self.s.ults)
               if u.state in ("likely", "possible") and u.ability.id not in exclude]
        order = {aid: i for i, aid in enumerate(self.data.abilities)}
        return sorted(ups, key=lambda u: (STATE_ORDER[u.state],
                                          TIER_ORDER.get(u.ability.tier, 9), order[u.ability.id]))

    @property
    def fights(self) -> list[tuple[str, int]]:
        return list(self.s.fights)

    @property
    def fight_uses(self) -> list[str]:
        return list(self.s.fight_uses)

    # --- what gets said ------------------------------------------------------------
    def _threat_phrase(self, now: float, exclude: tuple[str, ...] = (), limit: int = 3) -> str:
        ups = self.threats(now, exclude)
        if not ups:
            soonest = sorted(
                (u for u in (self.ult_status(a, now) for a in self.s.ults)
                 if u.state in ("charging", "used") and u.ability.id not in exclude),
                key=lambda u: u.possible_in)
            if soonest:
                u = soonest[0]
                secs = max(10, int(u.possible_in / 10.0 + 0.5) * 10)
                return f"Nothing likely up. {u.ability.aliases[0]} in about {secs} seconds."
            return "Nothing likely up."
        names = [u.ability.aliases[0] for u in ups[:limit]]
        more = f", plus {len(ups) - limit} more" if len(ups) > limit else ""
        up_ids = {u.ability.id for u in ups}
        combo = next((c for c in self.data.combos if up_ids.issuperset(c.ults)), None)
        watch = f" Watch for {combo.name}." if combo else ""
        return f"May have {_join(names)}{more}.{watch}"

    def status_line(self, now: float) -> str:
        if not self.s.ults:
            return "No enemy ults tracked."
        return self._threat_phrase(now)

    def fight_summary(self, used: list[str], now: float) -> str:
        """After a fight: what they spent, then what they may still have (coach order)."""
        if used:
            names = [self.data.get(a).aliases[0] for a in self._ordered(list(dict.fromkeys(used)))]
            spent = f"They used {_join(names)}."
        else:
            spent = "No enemy ults."
        if not self.s.ults:
            return spent
        return f"{spent} {self._threat_phrase(now, exclude=tuple(used))}"
