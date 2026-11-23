"""Match log: every call, with what the tool was estimating at that moment.

Lets you check the estimates against what really happened:
    python -m ow_assist --review       (last match)
    python -m ow_assist --review 5     (last 5 matches)

One JSON object per line in userdata/match_log.jsonl. Stays on your PC.
A new match starts when the app starts, on "reset"/"new match", and on "gg ...".
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import median

UNDOABLE = {"used", "cancelled", "reset", "round", "swapped", "seen", "fed", "fight", "result"}


class MatchLog:
    def __init__(self, path: Path | str, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.match = None  # wall time the current match started
        self._undo: list[tuple[str, float]] = []  # (kind, match it was logged in)

    def _write(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def new_match(self) -> None:
        self.match = round(self.clock(), 3)

    def record(self, kind: str, heard: str = "", ult: str | None = None,
               value=None, before=None, say: str | None = None, rates=None, **extra) -> None:
        """before: the tracker's UltStatus for `ult` just before this call (or None)."""
        if self.match is None:
            self.new_match()
        if kind == "undone" and self._undo:
            undone_kind, match = self._undo.pop()
            if undone_kind in ("reset", "result"):
                self.match = match  # undoing "gg loss" puts you back in that match
        elif kind in UNDOABLE:
            self._undo.append((kind, self.match))
            del self._undo[:-50]
        rec = {"t": round(self.clock(), 3), "m": self.match, "kind": kind, **extra}
        if heard:
            rec["heard"] = heard
        if ult:
            rec["ult"] = ult
        if value is not None:
            rec["value"] = value
        if say:
            rec["say"] = say
        if rates is not None:
            rec["rates"] = [round(rates.possible, 2), round(rates.likely, 2)]
        if before is not None:
            rec["before"] = {
                "anchor": before.anchor, "state": before.state,
                "elapsed": round(before.elapsed, 1), "charge": round(before.charge, 3),
                "possible_after": round(before.possible_after, 1),
                "likely_after": round(before.likely_after, 1),
            }
        self._write(rec)
        if kind in ("reset", "result"):
            self.new_match()


# --- review ----------------------------------------------------------------------

def read(path: Path | str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a half-written line from a crash
    return out


def _effective(records: list[dict]) -> list[dict]:
    """Drop records that were undone (undo pops the latest undoable record)."""
    kept: list[dict] = []
    for r in records:
        if r["kind"] == "undone":
            for i in range(len(kept) - 1, -1, -1):
                if kept[i]["kind"] in UNDOABLE:
                    del kept[i]
                    break
        else:
            kept.append(r)
    return kept


def _mmss(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def matches(records: list[dict]) -> list[list[dict]]:
    by: dict[float, list[dict]] = {}
    for r in records:
        by.setdefault(r["m"], []).append(r)
    return [by[m] for m in sorted(by) if any(r["kind"] in ("used", "seen") for r in by[m])]


def review_match(recs: list[dict], names: dict[str, str]) -> tuple[str, list[float], list[float]]:
    """Text report for one match, plus (gap/likely ratios, kill-cam charge errors)."""
    recs = _effective(recs)
    start, end = recs[0]["t"], recs[-1]["t"]
    uses = [r for r in recs if r["kind"] == "used" and r.get("ult")]
    fights = [r for r in recs if r["kind"] == "fight"]
    lines = [f"Match {time.strftime('%Y-%m-%d %H:%M', time.localtime(start))}, "
             f"{_mmss(end - start)} logged: {len(uses)} enemy ults called, {len(fights)} fights"
             + (f" (won {sum(f.get('value') == 'won' for f in fights)})" if fights else "")]

    ratios, early, late = [], [], []
    rows = []
    for r in uses:
        b = r.get("before")
        if not b or not b["likely_after"] or b["anchor"] == "seen":
            continue
        gap, pa, la = b["elapsed"], b["possible_after"], b["likely_after"]
        ratio = gap / la
        ratios.append(ratio)
        if gap < pa:
            verdict = "EARLY: back before 'may be up'"
            early.append(r)
        elif gap <= la:
            verdict = "in the window"
        elif gap <= 1.5 * la:
            verdict = "after 'likely' (held, or charged slowly)"
        else:
            verdict = "much later (held long, or a missed call?)"
            late.append(r)
        since = {"used": "used", "swap": "swap", "round": "round start"}.get(b["anchor"], b["anchor"])
        rows.append(f"  {names.get(r['ult'], r['ult']):24} {_mmss(gap):>5} after {since:11} "
                    f"may be up {_mmss(pa)}, likely {_mmss(la)}  -> {verdict}")
    if rows:
        lines.append("Ults used again (how long after the last time, vs the tool's window):")
        lines += rows

    errors = []
    cams = [r for r in recs if r["kind"] == "seen" and r.get("before")]
    if cams:
        lines.append("Kill cam checks (real charge vs the tool's estimate):")
        for r in cams:
            real, est = r["value"] / 100, r["before"]["charge"]
            errors.append(real - est)
            lines.append(f"  {names.get(r['ult'], r['ult']):24} real {real:4.0%}, "
                         f"tool {est:4.0%} ({'under' if real > est else 'over'} by {abs(real - est):.0%})")

    said = [r for r in recs if r["kind"] == "ult_possible"]
    if said:
        lines.append(f"'May be up' callouts: {len(said)}")
    if fights:
        per = [f.get("ults", 0) for f in fights]
        lines.append(f"Enemy ults per fight: {', '.join(map(str, per))}")
    return "\n".join(lines), ratios, errors


def advice(ratios: list[float], errors: list[float]) -> list[str]:
    out = []
    if len(ratios) >= 3:
        early = sum(r < 0.6 for r in ratios) / len(ratios)
        out.append(f"Repeat ults came back at {median(ratios):.2f}x the 'likely' time (median "
                   f"of {len(ratios)}). Below 1 means sooner than the tool expected.")
        if early >= 0.25:
            out.append("Ults often come back before 'may be up': the estimates are too slow. "
                       "Raise ult_possible_rate and ult_likely_rate by about 15%, or keep "
                       "playing and let the learning catch up.")
    if len(errors) >= 2:
        avg = sum(errors) / len(errors)
        if avg > 0.15:
            out.append(f"Kill cams showed {avg:.0%} more charge than estimated on average: "
                       "this lobby charges faster than the tool assumes.")
        elif avg < -0.15:
            out.append(f"Kill cams showed {-avg:.0%} less charge than estimated on average: "
                       "this lobby charges slower than the tool assumes.")
    if not out:
        out.append("Not enough repeat or kill-cam calls yet to judge the estimates. Calling "
                   "the same ult again when it's used, and kill-cam % when you die, gives "
                   "the most to compare.")
    return out


def report(path: Path | str, names: dict[str, str], last: int | None = 1) -> str:
    ms = matches(read(path))
    if not ms:
        return "No matches logged yet. Play with the app running, then try again."
    chosen = ms if last is None else ms[-last:]
    parts, ratios, errors = [], [], []
    for m in chosen:
        text, r, e = review_match(m, names)
        parts.append(text)
        ratios += r
        errors += e
    parts.append("Verdict:\n" + "\n".join(f"  - {a}" for a in advice(ratios, errors)))
    return "\n\n".join(parts)
