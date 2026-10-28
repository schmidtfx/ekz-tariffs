from __future__ import annotations

import datetime as dt

import pytest
from custom_components.ekz_tariffs.statistics import bucket_prices, day_slot_prices
from homeassistant.util import dt as dt_util

from tests.conftest import make_slots

# Europe/Zurich DST transitions: clocks go forward on the last Sunday in March
# (23h day) and back on the last Sunday in October (25h day).
SHORT_DAY = dt.date(2026, 3, 29)
LONG_DAY = dt.date(2026, 10, 25)
NORMAL_DAY = dt.date(2026, 6, 15)


def _local_midnight(day: dt.date) -> dt.datetime:
    return dt_util.start_of_local_day(
        dt_util.as_local(dt.datetime.combine(day, dt.time.min))
    )


@pytest.mark.asyncio
async def test_normal_day_has_96_buckets(hass_time_zone):
    slots = make_slots(_local_midnight(NORMAL_DAY), [0.2] * 96)
    assert len(day_slot_prices(slots, NORMAL_DAY)) == 96


@pytest.mark.asyncio
async def test_short_dst_day_has_92_buckets(hass_time_zone):
    """On the spring-forward day the local day is 23h = 92 quarter hours."""
    midnight = _local_midnight(SHORT_DAY)
    # Build slots across the whole real local day by walking absolute time.
    prices = day_slot_prices(make_slots(midnight, [0.2] * 100), SHORT_DAY)

    assert len(prices) == 92
    assert all(p == 0.2 for p in prices)


@pytest.mark.asyncio
async def test_long_dst_day_has_100_buckets(hass_time_zone):
    """On the fall-back day the local day is 25h = 100 quarter hours."""
    midnight = _local_midnight(LONG_DAY)
    prices = day_slot_prices(make_slots(midnight, [0.3] * 100), LONG_DAY)

    assert len(prices) == 100
    assert all(p == 0.3 for p in prices)


@pytest.mark.asyncio
async def test_short_dst_day_does_not_bleed_next_day(hass_time_zone):
    """Regression: a 24h-wide window used to pull 4 buckets from the next day."""
    midnight = _local_midnight(SHORT_DAY)
    next_midnight = _local_midnight(SHORT_DAY + dt.timedelta(days=1))

    # 23h of "today" at 0.2, then "tomorrow" at 0.9.
    today_slots = make_slots(midnight, [0.2] * 92)
    tomorrow_slots = make_slots(next_midnight, [0.9] * 96)

    prices, day_start = bucket_prices(today_slots + tomorrow_slots, SHORT_DAY)

    assert day_start == midnight
    assert len(prices) == 92
    assert 0.9 not in prices


@pytest.mark.asyncio
async def test_day_slot_prices_indexes_from_local_midnight(hass_time_zone):
    midnight = _local_midnight(NORMAL_DAY)
    # Publish only 08:00-09:00 -> buckets 32..35.
    slots = make_slots(midnight + dt.timedelta(hours=8), [0.3, 0.31, 0.32, 0.33])

    prices = day_slot_prices(slots, NORMAL_DAY)

    assert prices[31] is None
    assert prices[32:36] == [0.3, 0.31, 0.32, 0.33]
    assert prices[36] is None
