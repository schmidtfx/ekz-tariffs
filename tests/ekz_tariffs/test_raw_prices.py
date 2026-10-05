from __future__ import annotations

import datetime as dt
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.ekz_tariffs.sensor import EkzPriceSensor
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.conftest import make_slots


async def _setup_with_slots(hass, entry, slots):
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
        return_value=slots,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", "ekz_tariffs", f"{entry.entry_id}_integrated"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.mark.asyncio
async def test_forecast_contains_only_future_priced_slots(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    midnight = dt_util.start_of_local_day(fixed_now)
    prices = [round(0.10 + i / 1000, 6) for i in range(192)]
    slots = make_slots(midnight, prices)

    state = await _setup_with_slots(hass_time_zone, mock_config_entry, slots)
    forecast = state.attributes["forecast"]

    assert forecast[0] == [
        (midnight + dt.timedelta(minutes=49 * 15)).isoformat(),
        prices[49],
    ]
    assert forecast[-1] == [
        (midnight + dt.timedelta(days=1, minutes=95 * 15)).isoformat(),
        prices[-1],
    ]
    assert len(forecast) == 143
    assert all(dt_util.parse_datetime(start) > fixed_now for start, _ in forecast)
    assert [start for start, _ in forecast] == sorted(start for start, _ in forecast)
    assert await hass_time_zone.config_entries.async_unload(mock_config_entry.entry_id)
    await hass_time_zone.async_block_till_done()


@pytest.mark.asyncio
async def test_forecast_is_empty_without_future_data(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    start = fixed_now.replace(minute=0, second=0)
    slots = make_slots(start, [0.2])

    state = await _setup_with_slots(hass_time_zone, mock_config_entry, slots)

    assert state.attributes["forecast"] == []
    assert await hass_time_zone.config_entries.async_unload(mock_config_entry.entry_id)
    await hass_time_zone.async_block_till_done()


@pytest.mark.asyncio
async def test_forecast_has_common_attributes_and_is_unrecorded(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    start = fixed_now.replace(minute=0, second=0)
    slots = make_slots(
        start,
        [0.2, 0.21, 0.22, 0.23],
        feed_in=[0.08, 0.09, 0.10, 0.11],
    )
    hass = hass_time_zone
    await _setup_with_slots(hass, mock_config_entry, slots)

    registry = er.async_get(hass)
    expected_attributes = {
        "tariff_name",
        "publication_timestamp",
        "slot_start",
        "slot_end",
        "next_change",
        "forecast",
    }
    for suffix in ("integrated", "integrated_complete", "feed_in"):
        entity_id = registry.async_get_entity_id(
            "sensor", "ekz_tariffs", f"{mock_config_entry.entry_id}_{suffix}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert expected_attributes <= set(state.attributes)
        assert "forecast" in state.state_info["unrecorded_attributes"]
    for suffix in ("electricity", "grid", "regional_fees"):
        entity_id = registry.async_get_entity_id(
            "sensor", "ekz_tariffs", f"{mock_config_entry.entry_id}_{suffix}"
        )
        assert entity_id is not None
        assert (
            registry.async_get(entity_id).disabled_by
            == er.RegistryEntryDisabler.INTEGRATION
        )
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_all_price_components_share_the_same_attributes(
    hass_time_zone, patch_now, fixed_now
):
    start = fixed_now.replace(minute=0, second=0)
    slots = make_slots(start, [0.40, 0.50], feed_in=[0.05, 0.06])
    slots[0] = replace(
        slots[0],
        price_chf_per_kwh=0.36,
        integrated_chf_per_kwh=0.30,
        electricity_chf_per_kwh=0.10,
        grid_chf_per_kwh=0.20,
        regional_fees_chf_per_kwh=0.06,
    )
    coordinator = SimpleNamespace(
        data=slots,
        publication_timestamp=fixed_now,
        last_fetched=fixed_now,
    )
    expected_attributes = {
        "tariff_name",
        "publication_timestamp",
        "slot_start",
        "slot_end",
        "next_change",
        "forecast",
    }

    for component, expected_value in (
        ("electricity", 0.10),
        ("grid", 0.20),
        ("regional_fees", 0.06),
        ("integrated", 0.30),
        ("integrated_complete", 0.36),
        ("feed_in", 0.05),
    ):
        sensor = EkzPriceSensor(
            hass_time_zone,
            "entry",
            coordinator,
            component,
            f"tariff_{component}",
            True,
        )

        assert sensor.native_value == expected_value
        assert set(sensor.extra_state_attributes) == expected_attributes
        assert sensor._unrecorded_attributes == frozenset({"forecast"})
