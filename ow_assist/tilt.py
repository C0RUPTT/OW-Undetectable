"""Tilt tracker: session results, loss streaks, stop rules. Wall-clock time is passed in."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .commands import Command

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    started REAL NOT NULL,
    ended REAL
);
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    at REAL NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('win', 'loss', 'draw')),
    tilted INTEGER NOT NULL DEFAULT 0
);
"""


class Store:
    """Game history in a local SQLite file. Nothing leaves your PC."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript(SCHEMA)

    def start_session(self, at: float) -> int:
        with self.db:
            return self.db.execute("INSERT INTO sessions (started) VALUES (?)", (at,)).lastrowid

    def end_session(self, session_id: int, at: float) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET ended = ? WHERE id = ?", (at, session_id))

    def add_game(self, session_id: int, at: float, result: str, tilted: bool) -> int:
        with self.db:
            return self.db.execute(
                "INSERT INTO games (session_id, at, result, tilted) VALUES (?, ?, ?, ?)",
                (session_id, at, result, int(tilted)),
            ).lastrowid

    def delete_game(self, game_id: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM games WHERE id = ?", (game_id,))

    def games(self) -> list[tuple[int, float, str, bool]]:
        """(session_id, at, result, tilted) for every game, oldest first."""
        rows = self.db.execute(
            "SELECT session_id, at, result, tilted FROM games ORDER BY at, id"
        ).fetchall()
        return [(s, at, r, bool(t)) for s, at, r, t in rows]


@dataclass
class Game:
    id: int
    at: float
    result: str
    tilted: bool


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    h, m = divmod(minutes, 60)
    if not h:
        return f"{m} minutes"
    hours = f"{h} hour{'s' if h > 1 else ''}"
    return f"{hours} {m} minutes" if m else hours


class TiltTracker:
    def __init__(self, store: Store, warn_after: int = 2, stop_after: int = 3,
                 long_minutes: float = 120, gap_minutes: float = 60):
        self.store = store
        self.warn_after = warn_after
        self.stop_after = stop_after
        self.long_seconds = long_minutes * 60
        self.gap_seconds = gap_minutes * 60
        self.session_id: int | None = None
        self.started = 0.0
        self.games: list[Game] = []
        self.goal: int | None = None
        self.long_warned = False

    # --- session lifecycle ---------------------------------------------------
    def start_session(self, now: float) -> None:
        if self.session_id is not None:
            return
        self.session_id = self.store.start_session(now)
        self.started = now
        self.games, self.goal, self.long_warned = [], None, False

    def end_session(self, now: float) -> list[str]:
        if self.session_id is None:
            return []
        self.store.end_session(self.session_id, now)
        summary = [f"Session over. {self.record_phrase()}."] if self.games else []
        self.session_id = None
        self.games, self.goal, self.long_warned = [], None, False
        return summary

    # --- commands ------------------------------------------------------------
    def handle(self, cmd: Command, now: float) -> list[str]:
        if cmd.kind == "result":
            out = []
            if self.games and now - self.games[-1].at > self.gap_seconds:
                self.end_session(now)  # long break without the game closing: new session
            self.start_session(now)
            gid = self.store.add_game(self.session_id, now, cmd.value, cmd.tilted)
            self.games.append(Game(gid, now, cmd.value, cmd.tilted))
            out.append(self._after_result(cmd.value))
            return out
        if cmd.kind == "goal":
            self.start_session(now)
            self.goal = cmd.value or None
            return [f"Goal set: {self.goal} games." if self.goal else "Goal cleared."]
        if cmd.kind == "record":
            return [self.record_phrase() + "." if self.games else "No games logged yet."]
        raise ValueError(cmd.kind)

    def undo(self) -> list[str]:
        if not self.games:
            return ["Nothing to undo."]
        game = self.games.pop()
        self.store.delete_game(game.id)
        return [f"Removed last {game.result}."]

    # --- state ---------------------------------------------------------------
    @property
    def loss_streak(self) -> int:
        streak = 0
        for g in reversed(self.games):
            if g.result == "draw":
                continue
            if g.result != "loss":
                break
            streak += 1
        return streak

    def counts(self) -> tuple[int, int, int]:
        rs = [g.result for g in self.games]
        return rs.count("win"), rs.count("loss"), rs.count("draw")

    def record_phrase(self) -> str:
        w, l, d = self.counts()
        text = f"{w} {'win' if w == 1 else 'wins'}, {l} {'loss' if l == 1 else 'losses'}"
        if d:
            text += f", {d} {'draw' if d == 1 else 'draws'}"
        if self.loss_streak >= 2:
            text += f", {self.loss_streak} losses in a row"
        return text

    def _after_result(self, result: str) -> str:
        parts = [f"{result.capitalize()} logged."]
        streak = self.loss_streak
        if result == "loss" and streak >= self.stop_after:
            parts.append(f"{streak} losses in a row. Consider calling it.")
        elif result == "loss" and streak >= self.warn_after:
            parts.append(f"{streak} losses in a row.")
        if self.goal and len(self.games) == self.goal:
            parts.append(f"That's your {self.goal} games.")
        return " ".join(parts)

    def check(self, now: float) -> list[str]:
        """Called regularly; returns anything worth saying unprompted."""
        if self.session_id is None or self.long_warned:
            return []
        if now - self.started >= self.long_seconds:
            self.long_warned = True
            return [f"You've been playing for {_duration(now - self.started)}."]
        return []

    def status(self) -> str:
        if self.loss_streak >= self.stop_after or (self.goal and len(self.games) >= self.goal):
            return "red"
        if (self.loss_streak >= self.warn_after or self.long_warned
                or (self.games and self.games[-1].tilted)):
            return "yellow"
        return "green"

    def snapshot(self, now: float) -> dict:
        w, l, d = self.counts()
        return {
            "active": self.session_id is not None,
            "wins": w, "losses": l, "draws": d,
            "recent": [g.result[0].upper() for g in self.games[-10:]],
            "loss_streak": self.loss_streak,
            "status": self.status(),
            "goal": self.goal,
            "games": len(self.games),
            "minutes": int((now - self.started) // 60) if self.session_id is not None else 0,
        }
