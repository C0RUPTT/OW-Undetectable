import json

import pytest

from ow_assist import commands
from ow_assist.__main__ import Controller
from ow_assist.commands import Command
from ow_assist.data import DataError, load_abilities
from ow_assist.tracker import Tracker


@pytest.fixture
def data():
    return load_abilities()


def kinds(events):
    return [(e.kind, e.ability_id) for e in events]


def test_shipped_data_loads(data):
    assert data.alias_map["nade"] == "ana_nade"
    assert data.alias_map["amp matrix"] == "bap_ult"


def test_duplicate_alias_rejected(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"abilities": [
        {"id": "a", "kind": "ult", "hero": "X", "name": "A", "aliases": ["boom"]},
        {"id": "b", "kind": "ult", "hero": "Y", "name": "B", "aliases": ["Boom"]},
    ]}))
    with pytest.raises(DataError, match="boom"):
        load_abilities(p)


def test_reserved_word_alias_rejected(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"abilities": [
        {"id": "a", "kind": "ult", "hero": "X", "name": "A", "aliases": ["cancel it"]},
    ]}))
    with pytest.raises(DataError, match="reserved"):
        load_abilities(p)


@pytest.mark.parametrize("text,expected", [
    ("nade", Command("use", "ana_nade")),
    ("  Enemy  NADE ", Command("use", "ana_nade")),
    ("cancel sleep", Command("cancel", "ana_sleep")),
    ("cancel enemy grav", Command("cancel", "zarya_ult")),
    ("undo", Command("undo")),
    ("new round", Command("reset")),
    ("amp matrix", Command("use", "bap_ult")),
    ("[unk]", None),
    ("", None),
    ("banana", None),
])
def test_parse(data, text, expected):
    assert commands.parse(text, data) == expected


def test_grammar_covers_every_parseable_phrase(data):
    phrases = commands.grammar(data)
    assert phrases[-1] == "[unk]"
    for phrase in phrases[:-1]:
        assert commands.parse(phrase, data) is not None, phrase


def test_cooldown_warn_then_ready(data):
    t = Tracker(data, warn_before=3, call_lag=0)
    assert kinds(t.apply(Command("use", "ana_nade"), 100)) == [("used", "ana_nade")]
    assert t.poll(106) == []
    assert kinds(t.poll(107.5)) == [("warn", "ana_nade")]
    assert t.poll(108) == []  # warns only once
    assert kinds(t.poll(110)) == [("ready", "ana_nade")]
    assert t.status(110).cooldowns == []


def test_call_lag_shortens_remaining(data):
    t = Tracker(data, warn_before=0, call_lag=0.5)
    t.apply(Command("use", "ana_nade"), 100)
    (_, remaining), = t.status(100).cooldowns
    assert remaining == pytest.approx(9.5)


def test_after_effect_adds_duration(data):
    from ow_assist.data import Ability, AbilityData
    a = Ability("x", "cooldown", "H", "X", ("ex",), cooldown=10, starts="after_effect", effect=4)
    t = Tracker(AbilityData([a]), warn_before=0)
    t.apply(Command("use", "x"), 0)
    assert t.poll(13.9) == []
    assert kinds(t.poll(14)) == [("ready", "x")]


def test_recall_restarts_timer(data):
    t = Tracker(data, warn_before=3, call_lag=0)
    t.apply(Command("use", "ana_nade"), 0)
    t.poll(8)  # warned
    t.apply(Command("use", "ana_nade"), 9)
    assert kinds(t.poll(16)) == [("warn", "ana_nade")]
    assert kinds(t.poll(19)) == [("ready", "ana_nade")]


def test_ult_tracks_elapsed(data):
    t = Tracker(data, call_lag=0)
    t.apply(Command("use", "zarya_ult"), 10)
    (ability, elapsed), = t.status(58).ults
    assert ability.id == "zarya_ult" and elapsed == 48
    assert t.poll(1000) == []  # ults never fire ready cues


def test_cancel_undo_reset(data):
    t = Tracker(data, call_lag=0)
    t.apply(Command("use", "ana_nade"), 0)
    t.apply(Command("use", "zarya_ult"), 0)
    assert kinds(t.apply(Command("cancel", "ana_nade"), 1)) == [("cancelled", "ana_nade")]
    assert t.status(1).cooldowns == []
    assert kinds(t.apply(Command("undo"), 1)) == [("undone", None)]
    assert len(t.status(1).cooldowns) == 1
    t.apply(Command("reset"), 2)
    assert t.status(2).cooldowns == [] and t.status(2).ults == []
    t.apply(Command("undo"), 2)
    assert len(t.status(2).ults) == 1
    assert kinds(t.apply(Command("cancel", "ana_sleep"), 3)) == [("nothing", "ana_sleep")]


def test_undo_with_empty_history(data):
    assert kinds(Tracker(data).apply(Command("undo"), 0)) == [("nothing", None)]


class FakeSound:
    def __init__(self):
        self.events, self.unknowns = [], 0

    def handle(self, e):
        self.events.append((e.kind, e.ability_id))

    def unknown(self):
        self.unknowns += 1

    def close(self):
        pass


def make_controller(data, **overrides):
    settings = {"warn_before_seconds": 3, "call_lag_seconds": 0,
                "fire_on_partial": True, "buzz_on_unknown": False, "window_topmost": True}
    settings.update(overrides)
    sound = FakeSound()
    return Controller(data, settings, sound, log=lambda *_: None), sound


def test_partial_fires_once_and_final_is_deduped(data):
    c, sound = make_controller(data)
    c.on_text("nade", False)
    c.on_text("nade", False)
    c.on_text("nade", True)
    assert sound.events == [("used", "ana_nade")]


def test_final_fires_when_partials_disabled(data):
    c, sound = make_controller(data, fire_on_partial=False)
    c.on_text("nade", False)
    assert sound.events == []
    c.on_text("nade", True)
    assert sound.events == [("used", "ana_nade")]


def test_final_differs_from_partial(data):
    c, sound = make_controller(data)
    c.on_text("sleep", False)
    c.on_text("suzu", True)
    assert sound.events == [("used", "ana_sleep"), ("used", "kiriko_suzu")]


def test_unknown_buzz_only_when_enabled(data):
    c, sound = make_controller(data)
    c.on_text("[unk]", True)
    assert sound.unknowns == 0
    c, sound = make_controller(data, buzz_on_unknown=True)
    c.on_text("[unk]", True)
    assert sound.unknowns == 1
