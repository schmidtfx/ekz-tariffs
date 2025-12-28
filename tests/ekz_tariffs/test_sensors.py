from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er


@pytest.mark.asyncio
async def test_current_price_and_next_change_sensors(
    hass_time_zone,
    mock_config_entry,
    patch_now,
    fixed_now,
):
    hass = hass_time_zone
    mock_config_entry.add_to_hass(hass)

    # Build slots covering "now" and the next boundary.
    from tests.conftest import make_slots

    start = fixed_now.replace(minute=0, second=0)
    prices = [0.20, 0.20, 0.25, 0.25]  # 1 hour of data
    slots = make_slots(start, prices)

    # Patch API fetch to return our slots on first refresh.
    with patch(
        "custom_components.ekz_tariffs.api.EkzTariffsApi.fetch_tariffs",
        return_value=slots,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)

    # Find sensors by unique_id (most stable in tests)
    current_entity_id = None
    nextchange_entity_id = None
    for e in registry.entities.values():
        if e.config_entry_id != mock_config_entry.entry_id:
            continue
        if e.unique_id == f"{mock_config_entry.entry_id}_current_price":
            current_entity_id = e.entity_id
        if e.unique_id == f"{mock_config_entry.entry_id}_next_change":
            nextchange_entity_id = e.entity_id

    assert current_entity_id is not None
    assert nextchange_entity_id is not None

    # State now should be within the first slot price (0.20)
    cur = hass.states.get(current_entity_id)
    assert cur is not None
    assert float(cur.state) == 0.20

    nxt = hass.states.get(nextchange_entity_id)
    assert nxt is not None
    # Next change should be at end of the current 15-min slot:
    # fixed_now is at 11:07 -> boundary is 11:15
    print(nxt.state)
    assert "11:15:00" in nxt.state
