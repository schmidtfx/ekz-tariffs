from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from custom_components.ekz_tariffs.statistics import daily_stats
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.conftest import make_slots

NORMAL_DAY = dt.date(2026, 6, 15)
LONG_DAY = dt.date(2026, 10, 25)


def _local_midnight(day: dt.date) -> dt.datetime:
    return dt_util.start_of_local_day(
        dt_util.as_local(dt.datetime.combine(day, dt.time.min))
    )


def _slots_walking_real_time(start: dt.datetime, prices: list[float]):
    """Contiguous 15-minute slots stepped in UTC, so DST hours are not skipped."""
    from custom_components.ekz_tariffs.api import TariffSlot

    out = []
    cur = dt_util.as_utc(start)
    for p in prices:
        nxt = cur + dt.timedelta(minutes=15)
        out.append(
            TariffSlot(
                start=dt_util.as_local(cur),
                end=dt_util.as_local(nxt),
                price_chf_per_kwh=p,
                feed_in_chf_per_kwh=None,
            )
        )
        cur = nxt
    return out


@pytest.mark.asyncio
async def test_min_max_timestamps_point_at_the_extreme_slots(hass_time_zone):
    midnight = _local_midnight(NORMAL_DAY)
    prices = [0.20] * 96
    prices[8] = 0.05  # 02:00-02:15
    prices[70] = 0.90  # 17:30-17:45
    stats = daily_stats(make_slots(midnight, prices), NORMAL_DAY)

    assert stats["min"] == 0.05
    assert stats["min_start"] == midnight + dt.timedelta(hours=2)
    assert stats["min_end"] == midnight + dt.timedelta(hours=2, minutes=15)

    assert stats["max"] == 0.90
    assert stats["max_start"] == midnight + dt.timedelta(hours=17, minutes=30)
    assert stats["max_end"] == midnight + dt.timedelta(hours=17, minutes=45)


@pytest.mark.asyncio
async def test_span_covers_the_whole_contiguous_run(hass_time_zone):
    """A flat cheap block must report its full extent, not just the first slot."""
    midnight = _local_midnight(NORMAL_DAY)
    prices = [0.20] * 96
    prices[8:16] = [0.05] * 8  # 02:00-04:00
    stats = daily_stats(make_slots(midnight, prices), NORMAL_DAY)

    assert stats["min_start"] == midnight + dt.timedelta(hours=2)
    assert stats["min_end"] == midnight + dt.timedelta(hours=4)


@pytest.mark.asyncio
async def test_non_contiguous_ties_report_the_earliest_run(hass_time_zone):
    midnight = _local_midnight(NORMAL_DAY)
    prices = [0.20] * 96
    prices[8] = prices[9] = 0.05  # 02:00-02:30
    prices[60] = 0.05  # 15:00-15:15, same price, far away
    stats = daily_stats(make_slots(midnight, prices), NORMAL_DAY)

    assert stats["min_start"] == midnight + dt.timedelta(hours=2)
    assert stats["min_end"] == midnight + dt.timedelta(hours=2, minutes=30)


@pytest.mark.asyncio
async def test_timestamps_are_clamped_to_the_day(hass_time_zone):
    """A slot straddling midnight reports only the part inside the day."""
    midnight = _local_midnight(NORMAL_DAY)
    # One 3h slot from 23:00 the previous day, cheapest of the lot.
    overnight = make_slots(midnight - dt.timedelta(hours=1), [0.05], minutes=180)
    rest = make_slots(midnight + dt.timedelta(hours=2), [0.20] * 88)

    stats = daily_stats(overnight + rest, NORMAL_DAY)

    assert stats["min"] == 0.05
    assert stats["min_start"] == midnight
    assert stats["min_end"] == midnight + dt.timedelta(hours=2)


@pytest.mark.asyncio
async def test_timestamps_are_none_without_data(hass_time_zone):
    stats = daily_stats([], NORMAL_DAY)

    assert stats["min_start"] is None
    assert stats["min_end"] is None
    assert stats["max_start"] is None
    assert stats["max_end"] is None


@pytest.mark.asyncio
async def test_timestamps_resolve_the_repeated_dst_hour(hass_time_zone):
    """On the fall-back day 02:00-03:00 happens twice, at +02:00 then at +01:00."""
    prices = [0.20] * 100
    # Index 12 is 3h of real time past local midnight, i.e. the *second* 02:00.
    prices[12] = 0.05
    slots = _slots_walking_real_time(_local_midnight(LONG_DAY), prices)

    stats = daily_stats(slots, LONG_DAY)
    min_start = stats["min_start"]

    assert stats["min"] == 0.05
    assert min_start is not None
    assert min_start.hour == 2 and min_start.minute == 0
    assert min_start.utcoffset() == dt.timedelta(hours=1)


@pytest.mark.asyncio
async def test_quantiles_only_cover_the_requested_day(hass_time_zone):
    """Regression: median/quantiles used to be computed over *all* slots."""
    midnight = _local_midnight(NORMAL_DAY)
    today = make_slots(midnight, [0.20] * 96)
    tomorrow = make_slots(
        _local_midnight(NORMAL_DAY + dt.timedelta(days=1)), [0.90] * 96
    )

    stats = daily_stats(today + tomorrow, NORMAL_DAY)

    assert stats["median"] == 0.20
    assert stats["q25"] == 0.20
    assert stats["q75"] == 0.20


@pytest.mark.asyncio
async def test_average_sensor_exposes_extreme_timestamps(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)
    prices = [0.20] * 96
    prices[8] = 0.05
    prices[70] = 0.90
    slots = make_slots(midnight, prices)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
        return_value=slots,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = next(
        e.entity_id
        for e in registry.entities.values()
        if e.config_entry_id == mock_config_entry.entry_id
        and e.unique_id == f"{mock_config_entry.entry_id}_avg_today"
    )
    state = hass.states.get(entity_id)
    assert state is not None

    attrs = state.attributes
    assert attrs["min_price_chf_per_kwh"] == 0.05
    assert attrs["min_price_start"] == (midnight + dt.timedelta(hours=2)).isoformat()
    assert (
        attrs["min_price_end"]
        == (midnight + dt.timedelta(hours=2, minutes=15)).isoformat()
    )
    assert attrs["max_price_chf_per_kwh"] == 0.90
    assert (
        attrs["max_price_start"]
        == (midnight + dt.timedelta(hours=17, minutes=30)).isoformat()
    )
    assert (
        attrs["max_price_end"]
        == (midnight + dt.timedelta(hours=17, minutes=45)).isoformat()
    )
