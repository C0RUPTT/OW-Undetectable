import pytest

from ow_assist.ptt import BindingError, PushToTalkGate, parse_binding


@pytest.mark.parametrize("spec,expected", [
    ("mouse:x2", ("mouse", "x2")),
    (" Mouse:X1 ", ("mouse", "x1")),
    ("key:f13", ("key", "f13")),
    ("key:caps_lock", ("key", "caps_lock")),
    ("key:v", ("key", "v")),
])
def test_parse_binding(spec, expected):
    assert parse_binding(spec) == expected


@pytest.mark.parametrize("spec", ["x2", "mouse:left", "mouse:right", "pedal:1", "key:", "mouse:"])
def test_bad_bindings(spec):
    with pytest.raises(BindingError):
        parse_binding(spec)


def run(gate, script):
    """script: list of (block, held, now). Returns recognized blocks and finalize times."""
    recognized, finals = [], []
    for block, held, now in script:
        blocks, fin = gate.feed(block, held, now)
        recognized += blocks
        if fin:
            finals.append(now)
    return recognized, finals


def test_idle_audio_is_never_recognized():
    gate = PushToTalkGate(pre_roll_blocks=2)
    rec, fin = run(gate, [(b"a", False, 0.0), (b"b", False, 0.1), (b"c", False, 0.2)])
    assert rec == [] and fin == []


def test_press_includes_pre_roll_and_tail_then_finalizes():
    gate = PushToTalkGate(pre_roll_blocks=2, tail_seconds=0.3)
    rec, fin = run(gate, [
        (b"0", False, 0.0), (b"1", False, 0.1), (b"2", False, 0.2),  # pre-roll keeps last 2
        (b"3", True, 0.3), (b"4", True, 0.4),                         # held
        (b"5", False, 0.5),                                           # released: tail starts
        (b"6", False, 0.6), (b"7", False, 0.7),                       # still in tail
        (b"8", False, 0.8),                                           # tail over: finalize
        (b"9", False, 0.9),                                           # idle again
    ])
    assert rec == [b"1", b"2", b"3", b"4", b"5", b"6", b"7"]
    assert fin == [0.8]


def test_repress_during_tail_continues_same_utterance():
    gate = PushToTalkGate(pre_roll_blocks=0, tail_seconds=0.3)
    rec, fin = run(gate, [
        (b"a", True, 0.0), (b"b", False, 0.1), (b"c", True, 0.2),
        (b"d", False, 0.3), (b"e", False, 0.7),
    ])
    assert rec == [b"a", b"b", b"c", b"d"] and fin == [0.7]


def test_second_press_after_finalize_is_a_new_utterance():
    gate = PushToTalkGate(pre_roll_blocks=0, tail_seconds=0.1)
    _, fin = run(gate, [
        (b"a", True, 0.0), (b"b", False, 0.1), (b"c", False, 0.3),
        (b"d", True, 0.4), (b"e", False, 0.5), (b"f", False, 0.7),
    ])
    assert fin == [0.3, 0.7]
