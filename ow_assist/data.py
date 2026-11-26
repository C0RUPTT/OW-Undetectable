"""Load and validate ability data and user settings."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ABILITIES = ROOT / "data" / "abilities.json"
DEFAULT_SETTINGS = ROOT / "data" / "settings.json"
DEFAULT_HISTORY = ROOT / "userdata" / "history.sqlite3"

# Words the command parser owns; aliases may not use them.
RESERVED_WORDS = {"undo", "reset", "new", "round", "cancel", "enemy", "their",
                  "gg", "goal", "record"}

DEFAULT_SETTING_VALUES = {
    "call_lag_seconds": 0.5,
    "fire_on_partial": False,
    "min_confidence": 0.0,
    "require_enemy": False,
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


class AbilityData:
    def __init__(self, abilities: list[Ability]):
        self.abilities = {a.id: a for a in abilities}
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
    return Ability(
        id=aid, kind=kind, hero=hero, name=name, aliases=aliases,
        cooldown=cooldown, starts=starts, effect=float(raw.get("effect", 0)),
        custom_callout=raw.get("callout"),
    )


def load_abilities(path: Path | str = DEFAULT_ABILITIES) -> AbilityData:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [a.get("id") for a in raw["abilities"]]
    if len(ids) != len(set(ids)):
        raise DataError("duplicate ability ids")
    return AbilityData([_parse_ability(a) for a in raw["abilities"]])


def load_settings(path: Path | str = DEFAULT_SETTINGS) -> dict:
    settings = dict(DEFAULT_SETTING_VALUES)
    p = Path(path)
    if p.exists():
        user = json.loads(p.read_text(encoding="utf-8"))
        unknown = set(user) - set(settings)
        if unknown:
            raise DataError(f"unknown settings: {sorted(unknown)}")
        settings.update(user)
    return settings
