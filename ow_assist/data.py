"""Load and validate ability data and user settings."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ABILITIES = ROOT / "data" / "abilities.json"
DEFAULT_SETTINGS = ROOT / "data" / "settings.json"
# Your own overrides. Not in git, so updates never overwrite it.
MY_SETTINGS = ROOT / "my_settings.json"
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
    "model": "models/vosk-model-en-us-0.22-lgraph",
    "device": None,
    "phone": False,
    "turn_on": [],
    "turn_off": [],
    "cooldowns": {},
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
    enabled: bool = True

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
        enabled=bool(raw.get("enabled", True)),
    )


def load_library(path: Path | str = DEFAULT_ABILITIES) -> list[Ability]:
    """Every ability in the file, switched on or not. Aliases must be unique across all."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [a.get("id") for a in raw["abilities"]]
    if len(ids) != len(set(ids)):
        raise DataError("duplicate ability ids")
    library = [_parse_ability(a) for a in raw["abilities"]]
    AbilityData(library)  # alias clashes fail now, even between switched-off abilities
    return library


def apply_switches(library: list[Ability], turn_on=(), turn_off=(),
                   cooldowns=None) -> list[Ability]:
    """Override defaults from your settings: on/off, and cooldown seconds.

    Names can be an ability id or any of its aliases.
    """
    by_name = {a.id: a.id for a in library}
    by_name.update(AbilityData(library).alias_map)

    def find(name, where):
        aid = by_name.get(_normalize(str(name)))
        if aid is None:
            raise DataError(f"'{name}' in {where} isn't a known ability or alias "
                            "(see --list-abilities)")
        return aid

    switches = {}
    for names, value, where in ((turn_on, True, "turn_on"), (turn_off, False, "turn_off")):
        for name in names:
            switches[find(name, where)] = value
    seconds = {}
    for name, value in (cooldowns or {}).items():
        if not isinstance(value, (int, float)) or value <= 0:
            raise DataError(f"cooldowns: '{name}' needs a positive number of seconds")
        seconds[find(name, "cooldowns")] = float(value)
    return [replace(a, enabled=switches.get(a.id, a.enabled),
                    cooldown=seconds.get(a.id, a.cooldown)) for a in library]


def load_abilities(path: Path | str = DEFAULT_ABILITIES, turn_on=(), turn_off=(),
                   cooldowns=None) -> AbilityData:
    """The abilities that are switched on."""
    library = apply_switches(load_library(path), turn_on, turn_off, cooldowns)
    return AbilityData([a for a in library if a.enabled])


def load_settings(path: Path | str = DEFAULT_SETTINGS,
                  mine: Path | str | None = MY_SETTINGS) -> dict:
    """Defaults, then data/settings.json, then your my_settings.json on top."""
    settings = dict(DEFAULT_SETTING_VALUES)
    for p in (Path(path), Path(mine) if mine else None):
        if p is None or not p.exists():
            continue
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise DataError(f"{p.name} isn't valid JSON: {e}") from None
        unknown = set(user) - set(settings)
        if unknown:
            raise DataError(f"unknown settings in {p.name}: {sorted(unknown)}")
        settings.update(user)
    return settings
