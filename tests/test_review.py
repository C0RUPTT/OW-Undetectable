"""Match log, --review, and the mic test."""
import json

import pytest

from ow_assist import matchlog
from ow_assist.__main__ import Controller, main
from ow_assist.data import load_abilities
from ow_assist.matchlog import MatchLog
from ow_assist.mictest import MicTest, default_phrases, run


@pytest.fixture
def data():
    return load_abilities()


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class Quiet:
    def handle(self, e): pass
    def say(self, s): pass
    def close(self): pass


def controller(data, tmp_path, clock):
    log = MatchLog(tmp_path / "log.jsonl", clock=clock)
    c = Controller(data, {"call_lag_seconds": 0, "fire_on_partial": False,
                          "ult_learn_rates": False}, Quiet(), log=lambda *_: None,
                   match_log=log)
    return c, log


def records(log):
    return matchlog.read(log.path)


def test_calls_are_logged_with_the_estimate_before(data, tmp_path, monkeypatch):
    clock = Clock()
    mono = [100.0]
    monkeypatch.setattr("ow_assist.__main__.time.monotonic", lambda: mono[0])
    c, log = controller(data, tmp_path, clock)
    c.on_text("gravity", True)
    mono[0] += 200
    c.on_text("gravity", True)
    used = [r for r in records(log) if r["kind"] == "used"]
    assert len(used) == 2 and "before" not in used[0]
    b = used[1]["before"]
    assert b["anchor"] == "used" and b["elapsed"] == 200
    assert b["possible_after"] == pytest.approx(2500 / 16, abs=0.1)
    assert used[1]["rates"] == [16, 11]


def test_fight_logs_ult_count_and_nothing_is_skipped(data, tmp_path):
    c, log = controller(data, tmp_path, Clock())
    c.on_text("nano", True)
    c.on_text("blade", True)
    c.on_text("won fight", True)
    c.on_text("status", True)
    fight = [r for r in records(log) if r["kind"] == "fight"][0]
    assert fight["ults"] == 2 and fight["value"] == "won" and fight["say"].startswith("They used")
    assert any(r["kind"] == "status" for r in records(log))


def test_reset_and_gg_start_new_matches_and_undo_returns(data, tmp_path):
    from ow_assist.tilt import Store, TiltTracker
    clock = Clock()
    log = MatchLog(tmp_path / "log.jsonl", clock=clock)
    c = Controller(data, {"call_lag_seconds": 0, "fire_on_partial": False}, Quiet(),
                   TiltTracker(Store(":memory:")), log=lambda *_: None, match_log=log)
    c.speaker.say = lambda s: None
    c.on_text("nano", True)
    first = log.match
    clock.t += 10
    c.on_text("gg loss", True)
    assert log.match != first
    c.on_text("undo", True)            # undoing the result goes back to that match
    assert log.match == first
    clock.t += 10
    c.on_text("reset", True)
    assert log.match != first


def _write(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def _use(t, m, ult, elapsed=None, pa=156.2, la=227.3, anchor="used"):
    r = {"t": t, "m": m, "kind": "used", "ult": ult}
    if elapsed is not None:
        r["before"] = {"anchor": anchor, "state": "x", "elapsed": elapsed, "charge": 0.5,
                       "possible_after": pa, "likely_after": la}
    return r


def test_review_classifies_repeat_uses(tmp_path):
    p = tmp_path / "log.jsonl"
    _write(p, [
        _use(0, 0, "zarya_ult"),
        _use(100, 0, "zarya_ult", elapsed=100),     # before 'may be up'
        _use(300, 0, "zarya_ult", elapsed=200),     # in the window
        _use(800, 0, "zarya_ult", elapsed=500),     # much later
        {"t": 810, "m": 0, "kind": "fight", "value": "won", "ults": 2},
        {"t": 820, "m": 0, "kind": "seen", "ult": "ana_ult", "value": 90,
         "before": {"anchor": "used", "state": "x", "elapsed": 60, "charge": 0.4,
                    "possible_after": 140, "likely_after": 200}},
    ])
    text = matchlog.report(p, {"zarya_ult": "Zarya Graviton Surge", "ana_ult": "Ana Nano Boost"})
    assert "EARLY" in text and "in the window" in text and "missed call" in text
    assert "real  90%, tool  40% (under by 50%)" in text
    assert "Enemy ults per fight: 2" in text


def test_review_ignores_undone_calls(tmp_path):
    p = tmp_path / "log.jsonl"
    _write(p, [
        _use(0, 0, "zarya_ult"),
        _use(50, 0, "zarya_ult", elapsed=50),
        {"t": 51, "m": 0, "kind": "undone"},
    ])
    text = matchlog.report(p, {})
    assert "EARLY" not in text


def test_review_advice_when_ults_come_back_early():
    tips = matchlog.advice([0.4, 0.5, 0.5, 0.9], [0.3, 0.25])
    assert any("too slow" in t for t in tips)
    assert any("faster" in t for t in tips)
    assert "Not enough" in matchlog.advice([], [])[0]


def test_review_skips_matches_with_no_ult_calls(tmp_path):
    p = tmp_path / "log.jsonl"
    _write(p, [{"t": 0, "m": 0, "kind": "status"}])
    assert "No matches" in matchlog.report(p, {})
    assert "No matches" in matchlog.report(tmp_path / "missing.jsonl", {})


def test_review_tolerates_a_corrupt_line(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text(json.dumps(_use(0, 0, "zarya_ult")) + "\n{broken\n")
    assert "1 enemy ults called" in matchlog.report(p, {})


def test_review_cli(tmp_path, capsys):
    p = tmp_path / "log.jsonl"
    _write(p, [_use(0, 0, "zarya_ult")])
    assert main(["--review", "--match-log", str(p)]) == 0
    assert "Match " in capsys.readouterr().out


# --- mic test -------------------------------------------------------------------------

def test_mic_test_scores_ok_missed_and_wrong(data):
    t = MicTest(data, ["gravity", "valkyrie", "nano"])
    assert t.next_prompt() == "gravity"
    assert t.record("gravity") == "ok"
    assert t.record("bell") == "wrong"       # would log Kiriko's Suzu
    assert t.record("") == "missed"
    assert t.next_prompt() is None
    report = t.report()
    assert "1/3 heard correctly" in report
    assert "WRONG" in report and "'valkyrie'" in report and "bell" in report
    assert "MISSED" in report and "'nano'" in report


def test_mic_test_rounds_and_all_good(data):
    t = MicTest(data, ["gravity"], rounds=2)
    assert t.total == 2
    t.record("gravity")
    t.record("enemy gravity")              # same command, still right
    assert "Every call was heard right" in t.report()


def test_mic_test_rejects_unknown_words(data):
    with pytest.raises(ValueError, match="banana"):
        MicTest(data, ["banana"])


def test_default_phrases_cover_every_alias(data):
    phrases = default_phrases(data)
    assert set(data.alias_map) <= set(phrases)
    assert "won fight" in phrases and len(phrases) == len(set(phrases))


def test_run_loop_and_early_stop(data):
    t = MicTest(data, ["gravity", "nano", "blade"])
    answers = iter(["gravity", "nano"])

    def listen(_):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt

    out = []
    report = run(t, listen, out=out.append, pause=0)
    assert "2/2 heard correctly" in report
    assert any("Stopped early" in o for o in out)


def test_mic_test_cli_text_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _="": "gravity")
    rc = main(["--text", "--mic-test", "gravity", "--history", str(tmp_path / "h.sqlite3")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1/1 heard correctly" in out
    assert (tmp_path / "mic_test.txt").exists()
