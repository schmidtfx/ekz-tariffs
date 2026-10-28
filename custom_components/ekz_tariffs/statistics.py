from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TypedDict

from homeassistant.util import dt as dt_util

from .api import TariffSlot

BUCKET_MINUTES = 15


class DailyStats(TypedDict):
    avg: float | None
    min: float | None
    min_start: dt.datetime | None
    min_end: dt.datetime | None
    max: float | None
    max_start: dt.datetime | None
    max_end: dt.datetime | None
    median: float | None
    q25: float | None
    q75: float | None
    slots_count: int
    covered_minutes: int


def _day_range_local(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """Local midnight-to-midnight bounds for `day`.

    The end is the *next local midnight*, not start + 24h, so DST days span the
    real 23h/25h instead of bleeding into (or stopping short of) the next day.
    """
    start = dt_util.start_of_local_day(day)
    end = dt_util.start_of_local_day(day + dt.timedelta(days=1))
    return start, end


def _advance(moment: dt.datetime, delta: dt.timedelta) -> dt.datetime:
    """Add real elapsed time to a local datetime, re-normalising across DST.

    Adding a timedelta to an aware datetime keeps the original UTC offset
    (wall-clock arithmetic), so a plain `+` would skip or repeat the DST hour.
    """
    return dt_util.as_local(dt_util.as_utc(moment) + delta)


def daily_stats(slots: list[TariffSlot], day: dt.date) -> DailyStats:
    """Time-weighted average + min/max for a local day, based on overlap with that day."""
    day_start, day_end = _day_range_local(day)
    # Overlap maths must be in UTC; see the note in bucket_prices().
    start = dt_util.as_utc(day_start)
    end = dt_util.as_utc(day_end)

    total_weighted = 0.0
    total_seconds = 0.0

    min_p: float | None = None
    max_p: float | None = None
    # Spans are tracked in UTC and localised at the end: comparing two local
    # datetimes for contiguity would merge across the repeated DST hour.
    min_span: tuple[dt.datetime, dt.datetime] | None = None
    max_span: tuple[dt.datetime, dt.datetime] | None = None
    slots_count = 0
    vals: list[float] = []

    for s in sorted(slots, key=lambda s: s.start):
        a = max(dt_util.as_utc(s.start), start)
        b = min(dt_util.as_utc(s.end), end)

        if b <= a:
            continue

        seconds = (b - a).total_seconds()
        total_seconds += seconds
        total_weighted += s.price_chf_per_kwh * seconds

        p = float(s.price_chf_per_kwh)
        vals.append(p)

        # EKZ publishes 15-minute slots that routinely repeat a price (hence
        # fuse_slots()), so an extreme usually spans a block. Keep the earliest
        # such block and grow it while the price holds; `a`/`b` are clamped to
        # the day, so a slot straddling midnight reports only its in-day part.
        if min_p is None or p < min_p:
            min_p = p
            min_span = (a, b)
        elif p == min_p and min_span is not None and a == min_span[1]:
            min_span = (min_span[0], b)

        if max_p is None or p > max_p:
            max_p = p
            max_span = (a, b)
        elif p == max_p and max_span is not None and a == max_span[1]:
            max_span = (max_span[0], b)

        slots_count += 1

    avg = (total_weighted / total_seconds) if total_seconds > 0 else None
    covered_minutes = round(total_seconds / 60.0)

    vals.sort()

    return {
        "avg": avg,
        "min": min_p,
        "min_start": dt_util.as_local(min_span[0]) if min_span else None,
        "min_end": dt_util.as_local(min_span[1]) if min_span else None,
        "max": max_p,
        "max_start": dt_util.as_local(max_span[0]) if max_span else None,
        "max_end": dt_util.as_local(max_span[1]) if max_span else None,
        "median": _median(vals),
        "q25": _quantile(vals, q=0.25),
        "q75": _quantile(vals, q=0.75),
        "slots_count": slots_count,
        "covered_minutes": covered_minutes,
    }


@dataclass
class WindowResult:
    start: dt.datetime
    end: dt.datetime
    avg: float


def bucket_prices(
    slots: list[TariffSlot], day: dt.date
) -> tuple[list[float | None], dt.datetime]:
    day_start, day_end = _day_range_local(day)
    slots_sorted = sorted(slots, key=lambda s: s.start)

    # Walk the day in UTC. Comparing or incrementing datetimes that share the
    # same ZoneInfo falls back to wall-clock arithmetic, which would silently
    # skip (or repeat) an hour on DST transition days.
    bounds = [
        (dt_util.as_utc(s.start), dt_util.as_utc(s.end), s.price_chf_per_kwh)
        for s in slots_sorted
    ]

    prices: list[float | None] = []
    t = dt_util.as_utc(day_start)
    end = dt_util.as_utc(day_end)

    i = 0
    n = len(bounds)

    step = dt.timedelta(minutes=BUCKET_MINUTES)
    while t < end:
        while i < n and bounds[i][1] <= t:
            i += 1

        price: float | None = None
        if i < n:
            s_start, s_end, s_price = bounds[i]
            if s_start <= t < s_end:
                price = float(s_price)

        prices.append(price)
        t += step

    return prices, day_start


def day_slot_prices(slots: list[TariffSlot], day: dt.date) -> list[float | None]:
    """15-minute prices for a local day, indexed from local midnight.

    Length is 96 on a normal day, 92/100 on DST transition days. Buckets with no
    published price are None.
    """
    prices, _ = bucket_prices(slots, day)
    return prices


def _quantile(sorted_vals: list[float], q: float) -> float | None:
    """
    Linear-interpolated quantile on sorted values, q in [0,1].
    Returns None if empty.
    """
    if not sorted_vals:
        return None
    if q <= 0:
        return sorted_vals[0]
    if q >= 1:
        return sorted_vals[-1]

    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _median(sorted_vals: list[float]) -> float | None:
    return _quantile(sorted_vals, q=0.5)


def rolling_window_extreme(
    prices: list[float | None], day_start: dt.datetime, window_minutes: int, mode: str
) -> WindowResult | None:
    """
    Find lowest/highest continuous window based on bucket averages.
    Requires all buckets in the window are non-None.
    """
    if window_minutes % BUCKET_MINUTES != 0:
        raise ValueError("window_minutes must be a multiple of 15")

    k = window_minutes // BUCKET_MINUTES
    if k <= 0 or len(prices) < k:
        return None

    best_idx: int | None = None
    best_avg: float | None = None

    # sliding sum for speed, but must handle None
    window_sum = 0.0
    none_count = 0

    # init first window
    for j in range(k):
        v = prices[j]
        if v is None:
            none_count += 1
        else:
            window_sum += v

    def better(a: float, b: float) -> bool:
        return a < b if mode == "min" else a > b

    if none_count == 0:
        best_idx = 0
        best_avg = window_sum / k

    # slide
    for i in range(1, len(prices) - k + 1):
        out_v = prices[i - 1]
        in_v = prices[i + k - 1]

        if out_v is None:
            none_count -= 1
        else:
            window_sum -= out_v

        if in_v is None:
            none_count += 1
        else:
            window_sum += in_v

        if none_count == 0:
            avg = window_sum / k
            if best_avg is None or better(avg, best_avg):
                best_avg = avg
                best_idx = i

    if best_idx is None or best_avg is None:
        return None

    start = _advance(day_start, dt.timedelta(minutes=best_idx * BUCKET_MINUTES))
    end = _advance(start, dt.timedelta(minutes=window_minutes))
    return WindowResult(start=start, end=end, avg=best_avg)
