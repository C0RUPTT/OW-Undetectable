"""Ult estimates, calibration, swaps, rounds, fights and what gets said."""
import json

import pytest

from ow_assist import estimate
from ow_assist.__main__ import Controller, load_rates
from ow_assist.commands import Command
from ow_assist.data import DataError, load_abilities, load_settings
from ow_assist.tracker import Tracker

GRAV = Command("use", "zarya_ult")      # cost 2500, engage
NANO = Command("use", "ana_ult")        # cost 2300, kill
TRANS = Command("use", "zen_ult")       # cost 2500, save


@pytest.fixture
def data():
    return load_abilities()


def tracker(data, **kw):
    kw.setdefault("learn_rates", False)
    return Tracker(data, 0, possible_rate=20, likely_rate=10, **kw)


def test_every_ult_has_cost_and_tier_except_unknowns(data):
    for a in data.abilities.values():
        if a.kind == "ult" and a.id != "dmon_ult":
            assert 1000 <= a.cost <= 3500, a.id
    assert data.get("dmon_ult").cost == 0


def test_bad_tier_rejected(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"abilities": [
        {"id": "a", "kind": "ult", "hero": "X", "name": "A", "aliases": ["boom"], "tier": "huge"}]}))
    with pytest.raises(DataError, match="tier"):
        load_abilities(p)


def test_settings_reject_unknown_callout_tier(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"ult_callout_tiers": ["engage", "nope"]}))
    with pytest.raises(DataError, match="nope"):
        load_settings(p)


def test_states_progress(data):
    t = tracker(data)
    t.apply(GRAV, 0)               # 2500 pts: possible at 125 s, likely at 250 s
    assert t.ult_status("zarya_ult", 5).state == "used"
    u = t.ult_status("zarya_ult", 60)
    assert u.state == "charging" and u.possible_in == pytest.approx(65)
    assert t.ult_status("zarya_ult", 130).state == "possible"
    assert t.ult_status("zarya_ult", 250).state == "likely"
    assert t.ult_status("zarya_ult", 125).charge == pytest.approx(0.5)


def test_unknown_cost_only_shows_time(data):
    t = tracker(data)
    t.apply(Command("use", "dmon_ult"), 0)
    assert t.ult_status("dmon_ult", 5).state == "used"
    assert t.ult_status("dmon_ult", 999).state == "unknown"
    assert t.poll(999) == []


def test_swap_keeps_15_percent(data):
    t = tracker(data)
    t.apply(Command("swap", "zarya_ult"), 0)
    u = t.ult_status("zarya_ult", 0)
    assert u.anchor == "swap" and u.state == "charging"
    # (2500 - 375) / 20 = 106.25 s to possible
    assert u.possible_in == pytest.approx(106.25)


def test_swap_on_cooldown_clears_it(data):
    t = tracker(data)
    t.apply(Command("use", "ana_sleep"), 0)
    assert t.apply(Command("swap", "ana_sleep"), 1)[0].kind == "swapped"
    assert t.status(1).cooldowns == []
    assert t.apply(Command("swap", "ana_sleep"), 2)[0].kind == "nothing"


def test_new_round_zeroes_charge_but_keeps_comp(data):
    t = tracker(data)
    t.apply(GRAV, 0)
    t.apply(Command("use", "ana_sleep"), 0)
    assert t.apply(Command("round"), 500)[0].kind == "round"
    u = t.ult_status("zarya_ult", 510)
    assert u.anchor == "round" and u.elapsed == 10 and u.state == "charging"
    assert t.status(510).cooldowns == []
    t.apply(Command("undo"), 511)
    assert t.ult_status("zarya_ult", 511).anchor == "used"


def test_reset_forgets_comp(data):
    t = tracker(data)
    t.apply(GRAV, 0)
    t.apply(Command("reset"), 1)
    assert t.status(1).ults == []


def test_double_call_is_ignored(data):
    t = tracker(data, repeat_ignore=8)
    t.apply(GRAV, 0)
    assert t.apply(GRAV, 5)[0].kind == "nothing"
    assert t.ult_status("zarya_ult", 5).elapsed == 5  # not restarted
    assert t.apply(GRAV, 9)[0].kind == "used"


def test_possible_callout_once_and_grouped(data):
    t = tracker(data, callout_tiers=("engage", "kill"))
    t.apply(GRAV, 0)      # possible at 125
    t.apply(NANO, 10)     # 2300/20 = 115 -> possible at 125
    t.apply(TRANS, 0)     # save tier: never announced
    assert t.poll(100) == []
    ev, = t.poll(125)
    assert ev.kind == "ult_possible" and ev.say == "grav and nano may be up"
    assert t.poll(126) == [] and t.poll(1000) == []


def test_fight_summary_says_used_then_threats(data):
    t = tracker(data)
    t.apply(GRAV, 0)
    assert t.apply(Command("fight", value="won"), 20)[0].say.startswith("They used grav.")
    t.apply(NANO, 200)
    t.apply(Command("use", "genji_ult"), 200)
    ev, = t.apply(Command("fight", value="lost"), 210)
    # Grav (used at 0) is possible by 210; nano and blade were just used.
    assert ev.kind == "fight"
    assert ev.say == "They used nano and blade. May have grav."
    assert t.fights == [("won", 1), ("lost", 2)] and t.fight_uses == []
    ev, = t.apply(Command("fight", value="won"), 215)
    assert ev.say.startswith("No enemy ults. May have grav.")
    t.apply(Command("undo"), 216)
    assert t.fights == [("won", 1), ("lost", 2)]


def test_status_line(data):
    t = tracker(data)
    assert t.apply(Command("status"), 0)[0].say == "No enemy ults tracked."
    t.apply(GRAV, 0)
    assert t.apply(Command("status"), 1)[0].say == "Nothing likely up. grav in about 120 seconds."
    assert t.apply(Command("status"), 60)[0].say == "Nothing likely up. grav in about 70 seconds."
    t.apply(TRANS, 0)
    t.apply(NANO, 0)
    # likely before possible; then engage, kill, save
    assert t.apply(Command("status"), 240)[0].say == "May have nano, grav and trans."


def test_status_is_not_undoable(data):
    t = tracker(data)
    t.apply(GRAV, 0)
    t.apply(Command("status"), 1)
    t.apply(Command("undo"), 2)
    assert t.status(2).ults == []


def test_threat_list_caps_at_three(data):
    t = tracker(data)
    for a in ("zarya_ult", "ana_ult", "zen_ult", "genji_ult", "rein_ult"):
        t.apply(Command("use", a), 0)
    assert t.status_line(1000).endswith("plus 2 more.")


# --- calibration ---------------------------------------------------------------

def test_calibrated_defaults_without_samples():
    r = estimate.calibrated([], 16, 11)
    assert (r.possible, r.likely) == (16, 11)


def test_calibrated_moves_toward_observed():
    r = estimate.calibrated([20.0] * 20, 16, 11)
    assert 18 < r.likely < 20 and r.possible >= r.likely


def test_calibrated_never_below_passive():
    r = estimate.calibrated([1.0] * 50, 16, 11)
    assert r.likely >= estimate.PASSIVE_RATE


def test_observed_rate_filters():
    assert estimate.observed_rate(2500, 0, 10, 250) is None      # double call
    assert estimate.observed_rate(2500, 0, 1000, 250) is None    # missed a call
    assert estimate.observed_rate(2500, 0, 125, 250) == 20


def test_repeat_use_learns_rate(data):
    t = Tracker(data, 0, possible_rate=16, likely_rate=11, learn_rates=True)
    t.apply(GRAV, 0)
    t.apply(GRAV, 125)
    assert t.samples == [20]
    t.apply(Command("undo"), 126)
    assert t.samples == []


def test_controller_persists_rates(data, tmp_path):
    path = tmp_path / "rates.json"

    class Quiet:
        def handle(self, e): pass
        def say(self, s): pass
        def close(self): pass

    c = Controller(data, {"call_lag_seconds": 0, "fire_on_partial": False}, Quiet(),
                   log=lambda *_: None, rates_path=path)
    c.tracker.apply(GRAV, 0)
    c.tracker.apply(GRAV, 125)
    c.shutdown()
    assert load_rates(path) == [20]
    c2 = Controller(data, {"call_lag_seconds": 0}, Quiet(), log=lambda *_: None, rates_path=path)
    assert c2.tracker.samples == [20]


def test_load_rates_tolerates_garbage(tmp_path):
    p = tmp_path / "r.json"
    p.write_text("not json")
    assert load_rates(p) == []
    assert load_rates(tmp_path / "missing.json") == []


def test_snapshot_has_estimates(data):
    class Quiet:
        def handle(self, e): pass
        def say(self, s): pass
        def close(self): pass

    c = Controller(data, {"call_lag_seconds": 0, "fire_on_partial": False}, Quiet(),
                   log=lambda *_: None)
    c.on_text("grav", True)
    c.on_text("won fight", True)
    snap = c.ult_snapshot()
    u, = snap["ults"]
    assert u["state"] == "used" and u["tier"] == "engage" and 0 <= u["charge"] < 0.1
    assert snap["fights"] == [{"result": "won", "used": 1}] and snap["in_fight"] == 0
    assert snap["rates"]["samples"] == 0


# --- speech model vocabulary ------------------------------------------------------

def test_missing_words_and_unhearable(data):
    from ow_assist.voice import missing_words, unhearable

    class FakeModel:
        known = {"grav", "gravity", "nano", "enemy", "cancel", "swap"}

        def vosk_model_find_word(self, w):
            return 1 if w in self.known else -1

    missing = missing_words(FakeModel(), ["grav", "enemy nano", "nade", "[unk]"])
    assert missing == {"nade"}
    dead, deaf = unhearable(data, {"nade", "grav"})
    assert "nade" in dead and "grav" in dead
    assert "Ana Biotic Grenade" not in deaf      # "grenade" still works
    assert "Zarya Graviton Surge" not in deaf    # "gravity" still works
    _, deaf = unhearable(data, {"nano"})
    assert deaf == ["Ana Nano Boost"]
