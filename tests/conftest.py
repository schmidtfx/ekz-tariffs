from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from custom_components.ekz_tariffs.const import CONF_TARIFF_NAME, DOMAIN
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="EKZ 400D",
        data={CONF_TARIFF_NAME: "400D"},
        unique_id="ekz_tariffs_400D",
    )


@pytest.fixture
def hass_time_zone(hass):
    hass.config.set_time_zone("Europe/Zurich")
    return hass


def make_slots(start: dt.datetime, prices: list[float], minutes=15):
    """Create contiguous TariffSlot-like dicts."""
    from custom_components.ekz_tariffs.api import TariffSlot

    out = []
    cur = start
    for p in prices:
        nxt = cur + dt.timedelta(minutes=minutes)
        out.append(TariffSlot(start=cur, end=nxt, price_chf_per_kwh=p))
        cur = nxt
    return out


@pytest.fixture
def fixed_now():
    # A stable "now" inside today so sensors can evaluate current slot.
    return dt_util.as_local(
        dt.datetime(2025, 12, 28, 12, 7, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    )


@pytest.fixture
def patch_now(fixed_now):
    # Patch dt_util.now() used by your integration.
    with patch("homeassistant.util.dt.now", return_value=fixed_now):
        yield
