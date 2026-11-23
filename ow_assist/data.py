"""Load and validate ability data and user settings."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ABILITIES = ROOT / "data" / "abilities.json"
DEFAULT_SETTINGS = ROOT / "data" / "settings.json"
DEFAULT_HISTORY = ROOT / "userdata" / "history.sqlite3"
DEFAULT_RATES = ROOT / "userdata" / "ult_rates.json"
DEFAULT_MATCH_LOG = ROOT / "userdata" / "match_log.jsonl"

# Words the command parser owns; aliases may not use them.
RESERVED_WORDS = {"undo", "reset", "new", "round", "match", "cancel", "enemy", "their",
                  "gg", "goal", "record", "swap", "fight", "won", "lost", "status",
                  "full", "ten", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
                  "eighty", "ninety"}
TIERS = ("engage", "kill", "save", "minor")

DEFAULT_SETTING_VALUES = {
    "call_lag_seconds": 0.5,
    "fire_on_partial": True,
    "speech_rate": 230,
    "window_topmost": True,
    "phone_port": 8765,
    "push_to_talk": None,
    "ptt_tail_seconds": 0.3,
    "game_process": "Overwatch.exe",
    "warn_after_losses": 2,
    "stop_after_losses": 3,
    "long_session_minutes": 120,
    "session_end_grace_seconds": 120,
    "session_gap_minutes": 60,
    "ult_possible_rate": 16.0,
    "ult_likely_rate": 11.0,
    "ult_learn_rates": True,
    "ult_swap_kept_fraction": 0.15,
    "ult_repeat_ignore_seconds": 8.0,
    "ult_callout_tiers": ["engage", "kill"],
    "match_log": True,
}


class DataError(ValueError):
    pass


@dataclass(frozen=True)
class Ability:
    id: str
    kind: str  # "cooldown" or "ult"
    hero: str
    name: str
    aliases: tuple[str, ...]
    cooldown: float = 0.0
    starts: str = "on_use"
    effect: float = 0.0
    custom_callout: str | None = None
    cost: float = 0.0      # ult points; 0 = unknown, then only "time since used" is shown
    tier: str = "minor"    # ult priority: engage, kill, save or minor

    @property
    def recharge_seconds(self) -> float:
        """Seconds from the moment of use until the ability is ready again."""
        extra = self.effect if self.starts == "after_effect" else 0.0
        return self.cooldown + extra

    @property
    def callout(self) -> str:
        """What gets said when this cooldown is back."""
        return self.custom_callout or f"{self.aliases[0]} is up"

    @property
    def label(self) -> str:
        return f"{self.hero} {self.name}"


@dataclass(frozen=True)
class Combo:
    name: str                 # what gets said, e.g. "nano blade"
    ults: tuple[str, ...]     # ability ids that all need to be up


class AbilityData:
    def __init__(self, abilities: list[Ability], combos: list[Combo] | None = None):
        self.abilities = {a.id: a for a in abilities}
        self.combos = list(combos or [])
        self.alias_map: dict[str, str] = {}
        for a in abilities:
            for alias in a.aliases:
                if alias in self.alias_map:
                    other = self.alias_map[alias]
                    raise DataError(f"alias '{alias}' used by both {other} and {a.id}")
                self.alias_map[alias] = a.id

    def get(self, ability_id: str) -> Ability:
        return self.abilities[ability_id]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _parse_ability(raw: dict) -> Ability:
    try:
        aid, kind, hero, name = raw["id"], raw["kind"], raw["hero"], raw["name"]
        aliases = tuple(_normalize(a) for a in raw["aliases"])
    except KeyError as e:
        raise DataError(f"ability {raw.get('id', '?')} missing field {e}") from None
    if kind not in ("cooldown", "ult"):
        raise DataError(f"{aid}: kind must be 'cooldown' or 'ult'")
    if not aliases or any(not a for a in aliases):
        raise DataError(f"{aid}: needs at least one non-empty alias")
    for alias in aliases:
        clash = RESERVED_WORDS.intersection(alias.split())
        if clash:
            raise DataError(f"{aid}: alias '{alias}' uses reserved word(s) {sorted(clash)}")
    starts = raw.get("starts", "on_use")
    if starts not in ("on_use", "after_effect"):
        raise DataError(f"{aid}: starts must be 'on_use' or 'after_effect'")
    cooldown = float(raw.get("cooldown", 0))
    if kind == "cooldown" and cooldown <= 0:
        raise DataError(f"{aid}: cooldown abilities need a positive 'cooldown'")
    cost = float(raw.get("cost") or 0)
    if cost < 0:
        raise DataError(f"{aid}: cost can't be negative")
    tier = raw.get("tier", "minor")
    if tier not in TIERS:
        raise DataError(f"{aid}: tier must be one of {', '.join(TIERS)}")
    return Ability(
        id=aid, kind=kind, hero=hero, name=name, aliases=aliases,
        cooldown=cooldown, starts=starts, effect=float(raw.get("effect", 0)),
        custom_callout=raw.get("callout"), cost=cost, tier=tier,
    )


def load_abilities(path: Path | str = DEFAULT_ABILITIES) -> AbilityData:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [a.get("id") for a in raw["abilities"]]
    if len(ids) != len(set(ids)):
        raise DataError("duplicate ability ids")
    abilities = [_parse_ability(a) for a in raw["abilities"]]
    by_id = {a.id: a for a in abilities}
    combos = []
    for c in raw.get("combos", []):
        try:
            name, ults = c["name"], tuple(c["ults"])
        except (KeyError, TypeError):
            raise DataError(f"combo {c!r} needs 'name' and 'ults'") from None
        bad = [u for u in ults if u not in by_id or by_id[u].kind != "ult"]
        if len(ults) < 2 or bad:
            raise DataError(f"combo '{name}': needs 2+ known ult ids (bad: {bad})")
        combos.append(Combo(name, ults))
    return AbilityData(abilities, combos)


def load_settings(path: Path | str = DEFAULT_SETTINGS) -> dict:
    settings = dict(DEFAULT_SETTING_VALUES)
    p = Path(path)
    if p.exists():
        user = json.loads(p.read_text(encoding="utf-8"))
        unknown = set(user) - set(settings)
        if unknown:
            raise DataError(f"unknown settings: {sorted(unknown)}")
        settings.update(user)
    bad = set(settings["ult_callout_tiers"]) - set(TIERS)
    if bad:
        raise DataError(f"ult_callout_tiers: unknown tier(s) {sorted(bad)}")
    return settings
