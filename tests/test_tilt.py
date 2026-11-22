import pytest

from ow_assist import commands
from ow_assist.commands import Command
from ow_assist.data import load_abilities
from ow_assist.stats import report
from ow_assist.tilt import Store, TiltTracker
from ow_assist.watcher import GameWatch

WIN, LOSS, DRAW = (Command("result", value=v) for v in ("win", "loss", "draw"))
TILTED = Command("result", value="loss", tilted=True)


@pytest.fixture
def tilt():
    return TiltTracker(Store(":memory:"), warn_after=2, stop_after=3,
                       long_minutes=120, gap_minutes=60)


@pytest.mark.parametrize("text,expected", [
    ("gg win", WIN), ("gg loss", LOSS), ("gg draw", DRAW), ("gg loss tilted", TILTED),
    ("goal four games", Command("goal", value=4)), ("goal off", Command("goal", value=0)),
    ("goal eleven games", None), ("record", Command("record")), ("win", None),
])
def test_parse_tilt_commands(text, expected):
    assert commands.parse(text, load_abilities()) == expected


def test_grammar_includes_tilt_phrases():
    phrases = commands.grammar(load_abilities())
    assert {"gg win", "gg loss tilted", "goal four games", "record"} <= set(phrases)
    for phrase in phrases[:-1]:
        assert commands.parse(phrase, load_abilities()) is not None, phrase


def test_first_result_starts_session_and_confirms(tilt):
    assert tilt.session_id is None
    assert tilt.handle(WIN, 0) == ["Win logged."]
    assert tilt.session_id is not None


def test_loss_streak_warn_then_stop(tilt):
    tilt.handle(LOSS, 0)
    assert tilt.status() == "green"
    assert tilt.handle(LOSS, 600) == ["Loss logged. 2 losses in a row."]
    assert tilt.status() == "yellow"
    assert tilt.handle(LOSS, 1200) == ["Loss logged. 3 losses in a row. Consider calling it."]
    assert tilt.status() == "red"
    tilt.handle(WIN, 1800)
    assert tilt.loss_streak == 0 and tilt.status() == "green"


def test_draws_neither_break_nor_extend_streak(tilt):
    for c in (LOSS, DRAW, LOSS):
        tilt.handle(c, 0)
    assert tilt.loss_streak == 2


def test_tilted_flag_makes_status_yellow(tilt):
    tilt.handle(TILTED, 0)
    assert tilt.status() == "yellow"


def test_goal(tilt):
    assert tilt.handle(Command("goal", value=2), 0) == ["Goal set: 2 games."]
    tilt.handle(WIN, 1)
    assert tilt.handle(WIN, 2) == ["Win logged. That's your 2 games."]
    assert tilt.status() == "red"
    assert tilt.handle(Command("goal", value=0), 3) == ["Goal cleared."]


def test_record_phrase(tilt):
    assert tilt.handle(Command("record"), 0) == ["No games logged yet."]
    for c in (WIN, LOSS, LOSS, DRAW):
        tilt.handle(c, 0)
    assert tilt.handle(Command("record"), 0) == ["1 win, 2 losses, 1 draw, 2 losses in a row."]


def test_undo_removes_from_db(tilt):
    tilt.handle(WIN, 0)
    tilt.handle(LOSS, 1)
    assert tilt.undo() == ["Removed last loss."]
    assert [g[2] for g in tilt.store.games()] == ["win"]
    tilt.undo()
    assert tilt.undo() == ["Nothing to undo."]


def test_long_session_warns_once(tilt):
    tilt.start_session(0)
    assert tilt.check(119 * 60) == []
    assert tilt.check(120 * 60) == ["You've been playing for 2 hours."]
    assert tilt.check(150 * 60) == []
    assert tilt.status() == "yellow"


def test_long_gap_starts_new_session(tilt):
    tilt.handle(WIN, 0)
    first = tilt.session_id
    tilt.handle(LOSS, 61 * 60)
    assert tilt.session_id != first and len(tilt.games) == 1


def test_end_session_summary_and_reset(tilt):
    assert tilt.end_session(0) == []
    tilt.handle(WIN, 0)
    tilt.handle(LOSS, 1)
    assert tilt.end_session(2) == ["Session over. 1 win, 1 loss."]
    assert tilt.session_id is None and tilt.games == []


def test_history_persists_to_file(tmp_path):
    path = tmp_path / "h.sqlite3"
    t = TiltTracker(Store(path))
    t.handle(WIN, 0)
    t.handle(TILTED, 1)
    assert [(r, tl) for _, _, r, tl in Store(path).games()] == [("win", False), ("loss", True)]


def test_snapshot(tilt):
    tilt.handle(WIN, 0)
    tilt.handle(LOSS, 60)
    s = tilt.snapshot(300)
    assert s["active"] and s["recent"] == ["W", "L"] and s["minutes"] == 5
    assert (s["wins"], s["losses"], s["status"]) == (1, 1, "green")


def test_game_watch_grace():
    w = GameWatch(grace_seconds=120)
    assert w.update(False, 0) is None
    assert w.update(True, 10) == "start"
    assert w.update(True, 15) is None
    assert w.update(False, 60) is None      # crash/restart: within grace
    assert w.update(True, 100) is None      # back before grace ran out, same session
    assert w.update(False, 200) is None
    assert w.update(False, 220) == "stop"
    assert w.update(True, 300) == "start"


def test_stats_report():
    assert "No games" in report([])
    games = [(1, i, r, False) for i, r in enumerate(["loss", "loss", "win", "loss", "win"])]
    text = report(games)
    assert "Games: 5 across 1 sessions" in text
    assert "60%" not in text and "40%  (2W-3L)" in text
    assert "Next game after 2+ losses in a row: 100%  (1W-0L)" in text
    assert "Small sample" in text
