from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from custom_components.ekz_tariffs.const import EVENT_TARIFF_START, EVENT_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)


@pytest.mark.asyncio
async def test_calendar_fires_callback_event_on_start(
    hass: HomeAssistant, mock_config_entry
):
    await hass.config.async_set_time_zone("Europe/Zurich")
    mock_config_entry.add_to_hass(hass)

    # Choose a start in the future relative to patched "now"
    now = dt_util.as_local(
        dt.datetime(2025, 12, 28, 12, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    )
    start = now + dt.timedelta(minutes=30)  # 12:30
    # Two contiguous slots with same price -> fused into one event starting at 12:30
    from tests.conftest import make_slots

    slots = make_slots(start, [0.30, 0.30])
    events = async_capture_events(hass, EVENT_TYPE)

    with (
        patch("homeassistant.util.dt.now", return_value=now),
        patch(
            "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
            return_value=slots,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Fire time change to exactly event start
        async_fire_time_changed(hass, start)
        await hass.async_block_till_done()

    print(events)
    assert len(events) >= 1
    assert events[-1].data["type"] == EVENT_TARIFF_START
    assert events[-1].data["price_chf_per_kwh"] == 0.30
