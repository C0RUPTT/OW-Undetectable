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
    ("cancel enemy gravity", Command("cancel", "zarya_ult")),
    ("undo", Command("undo")),
    ("new round", Command("round")),
    ("new match", Command("reset")),
    ("reset", Command("reset")),
    ("swap gravity", Command("swap", "zarya_ult")),
    ("swap enemy nano", Command("swap", "ana_ult")),
    ("won fight", Command("fight", value="won")),
    ("fight lost", Command("fight", value="lost")),
    ("status", Command("status")),
    ("gravity", Command("use", "zarya_ult")),
    ("blackout", Command("use", "sombra_ult")),
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


def test_cooldown_ready(data):
    t = Tracker(data, call_lag=0)
    assert kinds(t.apply(Command("use", "ana_nade"), 100)) == [("used", "ana_nade")]
    assert t.poll(109.9) == []
    assert kinds(t.poll(110)) == [("ready", "ana_nade")]
    assert t.poll(111) == []  # announced once
    assert t.status(110).cooldowns == []


def test_call_lag_shortens_remaining(data):
    t = Tracker(data, call_lag=0.5)
    t.apply(Command("use", "ana_nade"), 100)
    (_, remaining), = t.status(100).cooldowns
    assert remaining == pytest.approx(9.5)


def test_after_effect_adds_duration(data):
    from ow_assist.data import Ability, AbilityData
    a = Ability("x", "cooldown", "H", "X", ("ex",), cooldown=10, starts="after_effect", effect=4)
    t = Tracker(AbilityData([a]))
    t.apply(Command("use", "x"), 0)
    assert t.poll(13.9) == []
    assert kinds(t.poll(14)) == [("ready", "x")]


def test_recall_restarts_timer(data):
    t = Tracker(data, call_lag=0)
    t.apply(Command("use", "ana_nade"), 0)
    t.apply(Command("use", "ana_nade"), 9)
    assert t.poll(18) == []
    assert kinds(t.poll(19)) == [("ready", "ana_nade")]


def test_ult_tracks_elapsed(data):
    t = Tracker(data, call_lag=0, callout_tiers=())
    t.apply(Command("use", "zarya_ult"), 10)
    u, = t.status(58).ults
    assert u.ability.id == "zarya_ult" and u.elapsed == 48 and u.anchor == "used"
    assert t.poll(1000) == []  # no ready cues when ult callouts are off


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


class FakeSpeaker:
    def __init__(self):
        self.events = []

    def handle(self, e):
        self.events.append((e.kind, e.ability_id))

    def close(self):
        pass


def make_controller(data, **overrides):
    settings = {"call_lag_seconds": 0, "fire_on_partial": True,
                "speech_rate": 230, "window_topmost": True}
    settings.update(overrides)
    speaker = FakeSpeaker()
    return Controller(data, settings, speaker, log=lambda *_: None), speaker


def test_partial_fires_once_and_final_is_deduped(data):
    c, sp = make_controller(data)
    c.on_text("nade", False)
    c.on_text("nade", False)
    c.on_text("nade", True)
    assert sp.events == [("used", "ana_nade")]


def test_final_fires_when_partials_disabled(data):
    c, sp = make_controller(data, fire_on_partial=False)
    c.on_text("nade", False)
    assert sp.events == []
    c.on_text("nade", True)
    assert sp.events == [("used", "ana_nade")]


def test_final_differs_from_partial(data):
    c, sp = make_controller(data)
    c.on_text("sleep", False)
    c.on_text("bell", True)
    assert sp.events == [("used", "ana_sleep"), ("used", "kiriko_suzu")]


def test_what_gets_said(data):
    from ow_assist.speech import phrase_for
    from ow_assist.tracker import Event
    assert phrase_for(Event("ready", "ana_sleep"), data) == "sleep is up"
    assert phrase_for(Event("used", "ana_sleep"), data) is None  # no confirmation on calls
    assert phrase_for(Event("undone"), data) == "undone"
    assert phrase_for(Event("reset"), data) == "cleared"
    assert phrase_for(Event("nothing"), data) is None


def test_custom_callout(tmp_path):
    import json
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"abilities": [
        {"id": "a", "kind": "cooldown", "hero": "Ana", "name": "Sleep", "aliases": ["sleep"],
         "cooldown": 14, "callout": "sleep ready"}]}))
    assert load_abilities(p).get("a").callout == "sleep ready"


def test_ult_snapshot_is_stable_order(data):
    c, _ = make_controller(data)
    c.on_text("gravity", True)   # zarya_ult comes after ana_ult in the data file
    c.on_text("nano", True)
    snap = c.ult_snapshot()
    assert [u["id"] for u in snap["ults"]] == ["ana_ult", "zarya_ult"]
    assert snap["ults"][0]["name"] == "Nano Boost" and snap["ults"][0]["elapsed"] >= 0


def test_phone_server_serves_page_and_status(data):
    import urllib.request
    from ow_assist.phone import PhoneServer
    c, _ = make_controller(data)
    c.on_text("gravity", True)
    server = PhoneServer(c.ult_snapshot, port=0, host="127.0.0.1")
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Enemy ults" in page
        status = json.loads(urllib.request.urlopen(base + "/status").read())
        assert status["ults"][0]["id"] == "zarya_ult"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/nope")
    finally:
        server.stop()


def test_undo_goes_to_most_recent_action(data):
    from ow_assist.tilt import Store, TiltTracker
    tilt = TiltTracker(Store(":memory:"))
    sp = FakeSpeaker()
    sp.said = []
    sp.say = sp.said.append
    settings = {"call_lag_seconds": 0, "fire_on_partial": False}
    c = Controller(data, settings, sp, tilt, log=lambda *_: None)
    c.on_text("nade", True)
    c.on_text("gg loss", True)
    c.on_text("undo", True)              # removes the loss, not the nade
    assert tilt.games == [] and len(c.tracker.status(0).cooldowns) == 1
    c.on_text("undo", True)              # now the nade
    assert c.tracker.status(0).cooldowns == []
    assert sp.said == ["Loss logged.", "Removed last loss."]
    assert c.ult_snapshot()["session"]["active"]
