"""Plain-text stats report: python -m ow_assist --stats"""
from __future__ import annotations

from collections import defaultdict

SMALL_SAMPLE = 30


def _rate(results: list[str]) -> str:
    w, l = results.count("win"), results.count("loss")
    if not w + l:
        return "no data"
    return f"{w / (w + l):.0%}  ({w}W-{l}L)"


def report(games: list[tuple[int, float, str, bool]]) -> str:
    """games: (session_id, at, result, tilted), oldest first."""
    if not games:
        return "No games logged yet. Say 'gg win' / 'gg loss' after each game."
    sessions = defaultdict(list)
    for sid, _at, result, tilted in games:
        sessions[sid].append((result, tilted))

    after_streak, after_tilted = [], []
    by_index = {"games 1-3": [], "games 4-6": [], "games 7+": []}
    for results in sessions.values():
        streak = 0
        for i, (result, tilted) in enumerate(results):
            if streak >= 2:
                after_streak.append(result)
            if i and results[i - 1][1]:
                after_tilted.append(result)
            bucket = "games 1-3" if i < 3 else "games 4-6" if i < 6 else "games 7+"
            by_index[bucket].append(result)
            if result == "loss":
                streak += 1
            elif result == "win":
                streak = 0

    all_results = [r for _, _, r, _ in games]
    lines = [
        f"Games: {len(games)} across {len(sessions)} sessions",
        f"Overall win rate:            {_rate(all_results)}",
        "",
        "Win rate by game number in a session:",
        *(f"  {k:<10} {_rate(v)}" for k, v in by_index.items()),
        "",
        f"Next game after 2+ losses in a row: {_rate(after_streak)}",
        f"Next game after a 'tilted' loss:    {_rate(after_tilted)}",
    ]
    if len(games) < SMALL_SAMPLE:
        lines += ["", f"Small sample: treat these as rough until you have {SMALL_SAMPLE}+ games."]
    return "\n".join(lines)
