from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from custom_components.ekz_tariffs.api import EkzTariffsApi
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.conftest import make_slots


@pytest.mark.asyncio
async def test_feed_in_price_sensor_with_schedule(
    hass_time_zone,
    mock_config_entry,
    patch_now,
    fixed_now,
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
    entity_id = None
    for e in registry.entities.values():
        if (
            e.config_entry_id == mock_config_entry.entry_id
            and e.unique_id == f"{mock_config_entry.entry_id}_feed_in_price"
        ):
            entity_id = e.entity_id

    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    # fixed_now is at 12:07 -> inside the second slot (12:00-12:15)
    assert float(state.state) == 0.08

    attrs = state.attributes
    assert attrs["slot_start"] == start.isoformat()
    assert attrs["slot_end"] == (start + dt.timedelta(minutes=15)).isoformat()

    schedule = attrs["schedule"]
    assert len(schedule) == 4
    assert schedule[0] == {
        "start": start.isoformat(),
        "end": (start + dt.timedelta(minutes=15)).isoformat(),
        "feed_in_chf_per_kwh": 0.08,
    }
    assert schedule[3]["feed_in_chf_per_kwh"] == 0.10
    assert attrs["next_change"] == (start + dt.timedelta(minutes=15)).isoformat()


def test_parse_slots_extracts_feed_in():
    api = EkzTariffsApi(session=None)
    base = dt_util.as_local(dt.datetime(2025, 12, 28, 0, 0, 0))
    data = {
        "prices": [
            {
                "start_timestamp": base.isoformat(),
                "end_timestamp": (base + dt.timedelta(minutes=15)).isoformat(),
                "integrated": [{"unit": "CHF_kWh", "value": 0.25}],
                "feed_in": [{"unit": "CHF_kWh", "value": 0.08}],
            },
            {
                "start_timestamp": (base + dt.timedelta(minutes=15)).isoformat(),
                "end_timestamp": (base + dt.timedelta(minutes=30)).isoformat(),
                "integrated": [{"unit": "CHF_kWh", "value": 0.26}],
                "feed_in": [],
            },
        ]
    }

    slots = api._parse_tariff_slots(data)

    assert len(slots) == 2
    assert slots[0].price_chf_per_kwh == 0.25
    assert slots[0].feed_in_chf_per_kwh == 0.08
    assert slots[1].feed_in_chf_per_kwh is None


def test_parse_slots_feed_in_with_vat():
    api = EkzTariffsApi(session=None)
    base = dt_util.as_local(dt.datetime(2025, 12, 28, 0, 0, 0))
    data = {
        "prices": [
            {
                "start_timestamp": base.isoformat(),
                "end_timestamp": (base + dt.timedelta(minutes=15)).isoformat(),
                "integrated": [{"unit": "CHF_kWh", "value": 0.25}],
                "feed_in": [{"unit": "CHF_kWh", "value": 0.10}],
            }
        ]
    }

    slots = api._parse_tariff_slots(data, incl_vat=True)

    from custom_components.ekz_tariffs.const import VAT_RATE

    assert slots[0].feed_in_chf_per_kwh == round(0.10 * (1 + VAT_RATE), 4)
