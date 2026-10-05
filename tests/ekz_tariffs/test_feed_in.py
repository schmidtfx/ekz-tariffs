from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from tests.conftest import make_slots


@pytest.mark.asyncio
async def test_feed_in_sensor_uses_shared_forecast_attributes(
    hass_time_zone, mock_config_entry, patch_now, fixed_now
):
    hass = hass_time_zone
    mock_config_entry.add_to_hass(hass)
    start = fixed_now.replace(minute=0, second=0)
    slots = make_slots(
        start,
        [0.20, 0.21, 0.25, 0.26],
        feed_in=[0.08, 0.08, 0.09, 0.10],
    )

    with patch(
        "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
        return_value=slots,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", "ekz_tariffs", f"{mock_config_entry.entry_id}_feed_in"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 0.08

    attrs = state.attributes
    assert {
        "tariff_name",
        "publication_timestamp",
        "slot_start",
        "slot_end",
        "next_change",
        "forecast",
    } <= set(attrs)
    assert attrs["slot_start"] == start.isoformat()
    assert attrs["slot_end"] == (start + dt.timedelta(minutes=15)).isoformat()
    assert attrs["forecast"] == [
        [(start + dt.timedelta(minutes=15 * idx)).isoformat(), price]
        for idx, price in ((1, 0.08), (2, 0.09), (3, 0.10))
    ]
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
