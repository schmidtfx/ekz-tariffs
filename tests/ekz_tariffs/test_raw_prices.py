from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.conftest import make_slots


async def _setup_with_slots(hass, entry, slots):
    """Set up the entry with `slots` and return the current price sensor state."""
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
        return_value=slots,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = None
    for e in registry.entities.values():
        if (
            e.config_entry_id == entry.entry_id
            and e.unique_id == f"{entry.entry_id}_current_price"
        ):
            entity_id = e.entity_id

    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.mark.asyncio
async def test_raw_today_and_tomorrow_are_full_days(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)

    # 96 slots today + 96 slots tomorrow, each distinguishable by index.
    today_prices = [round(0.10 + i / 1000, 6) for i in range(96)]
    tomorrow_prices = [round(0.50 + i / 1000, 6) for i in range(96)]
    slots = make_slots(midnight, today_prices + tomorrow_prices)

    state = await _setup_with_slots(hass, mock_config_entry, slots)
    attrs = state.attributes

    assert attrs["raw_today"] == today_prices
    assert attrs["raw_tomorrow"] == tomorrow_prices
    # index 0 is local midnight, so the 12:07 "now" falls in bucket 48
    assert attrs["raw_today"][48] == today_prices[48]
    assert float(state.state) == today_prices[48]


@pytest.mark.asyncio
async def test_raw_tomorrow_is_null_padded_before_publication(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)
    slots = make_slots(midnight, [0.2] * 96)

    state = await _setup_with_slots(hass, mock_config_entry, slots)
    attrs = state.attributes

    assert attrs["raw_today"] == [0.2] * 96
    # Full-length list of None, not an empty list or a missing key.
    assert attrs["raw_tomorrow"] == [None] * 96


@pytest.mark.asyncio
async def test_partial_data_yields_none_holes(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)
    # Only 08:00-09:00 published (buckets 32..35).
    slots = make_slots(midnight + dt.timedelta(hours=8), [0.3, 0.31, 0.32, 0.33])

    state = await _setup_with_slots(hass, mock_config_entry, slots)
    raw_today = state.attributes["raw_today"]

    assert len(raw_today) == 96
    assert raw_today[31] is None
    assert raw_today[32:36] == [0.3, 0.31, 0.32, 0.33]
    assert raw_today[36] is None


@pytest.mark.asyncio
async def test_publication_timestamp_is_aware(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)
    slots = make_slots(midnight, [0.2] * 96)

    state = await _setup_with_slots(hass, mock_config_entry, slots)

    published = dt_util.parse_datetime(state.attributes["publication_timestamp"])
    assert published is not None
    assert published.tzinfo is not None


@pytest.mark.asyncio
async def test_raw_arrays_are_excluded_from_recorder(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    """The arrays are large and change every 15 min; they must not be recorded."""
    hass = hass_time_zone
    midnight = dt_util.start_of_local_day(fixed_now)
    slots = make_slots(midnight, [0.2] * 96)

    state = await _setup_with_slots(hass, mock_config_entry, slots)

    assert state.state_info is not None
    excluded = state.state_info["unrecorded_attributes"]
    assert "raw_today" in excluded
    assert "raw_tomorrow" in excluded
