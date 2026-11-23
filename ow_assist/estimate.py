"""When might an enemy ult be back? Pure functions, no clock.

The model comes from how coaches teach ult tracking (see docs/ult-tracking.md):

- Every hero gains about 5 ult points per second passively, plus points for damage
  and healing. Real matches land at roughly 2-3x the passive rate.
- So an ult used at time T is *possible* again after cost / fast_rate seconds and
  *likely* after cost / typical_rate seconds. We never claim it IS up: we only know
  when it was used, not how much damage that player has done since.
- A hero swap keeps at most 15% of the new hero's cost, and a new round starts at 0.
- Repeat calls of the same ult tell us how fast this lobby actually charges, so the
  rates are tuned from your own games ("calibration").
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

PASSIVE_RATE = 5.0          # ult points per second every hero gets for free
MAX_RATE = 40.0             # anything faster than this was a mis-call
DEFAULT_POSSIBLE_RATE = 16.0
DEFAULT_LIKELY_RATE = 11.0
PRIOR_WEIGHT = 5            # learned rates need about this many samples to dominate
MIN_SAMPLE_SECONDS = 20.0   # two calls closer than this are a double call, not two ults
MISSED_CALL_FACTOR = 2.5    # a gap this many times the "likely" time probably hides a missed call
MAX_SAMPLES = 60

STATES = ("used", "charging", "possible", "likely", "unknown")


@dataclass(frozen=True)
class Rates:
    possible: float  # points/s that would make the ult come back early
    likely: float    # points/s of a typical player


def _quantile(values: list[float], q: float) -> float:
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _clamp(x: float) -> float:
    return max(PASSIVE_RATE, min(MAX_RATE, x))


def calibrated(samples: list[float], possible_default: float = DEFAULT_POSSIBLE_RATE,
               likely_default: float = DEFAULT_LIKELY_RATE) -> Rates:
    """Blend the defaults with rates observed in your games.

    Observed gaps between two uses include time the enemy held the ult, so observed
    rates run slow. The median is used as the typical rate and the 80th percentile
    as the early one.
    """
    if not samples:
        return Rates(possible_default, likely_default)
    w = len(samples) / (len(samples) + PRIOR_WEIGHT)
    likely = (1 - w) * likely_default + w * median(samples)
    possible = (1 - w) * possible_default + w * _quantile(samples, 0.8)
    likely = _clamp(likely)
    return Rates(max(_clamp(possible), likely), likely)


def window(cost: float, start_points: float, rates: Rates) -> tuple[float, float]:
    """Seconds after the anchor at which the ult becomes possible / likely."""
    need = max(0.0, cost - start_points)
    return need / rates.possible, need / rates.likely


def observed_rate(cost: float, start_points: float, seconds: float,
                  likely_after: float) -> float | None:
    """Rate implied by an ult being used again `seconds` after its anchor, if trustworthy."""
    if seconds < MIN_SAMPLE_SECONDS or seconds > MISSED_CALL_FACTOR * likely_after:
        return None
    rate = (cost - start_points) / seconds
    return rate if PASSIVE_RATE <= rate <= MAX_RATE else None


def state(elapsed: float, anchor: str, possible_after: float, likely_after: float,
          fresh_seconds: float = 15.0) -> str:
    if anchor == "used" and elapsed < fresh_seconds:
        return "used"
    if elapsed >= likely_after:
        return "likely"
    if elapsed >= possible_after:
        return "possible"
    return "charging"
