from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import AsyncMock

import pytest
from custom_components.ekz_tariffs.api import EkzTariffsApi, EkzTariffsOAuthApi
from custom_components.ekz_tariffs.const import API_BASE, API_TARIFFS_PATH
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util


def _component_response(
    start: dt.datetime,
    end: dt.datetime,
    component: str,
    value: float,
    publication_timestamp: dt.datetime | None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "prices": [
            {
                "start_timestamp": start.isoformat(),
                "end_timestamp": end.isoformat(),
                component: [{"unit": "CHF_kWh", "value": value}],
            }
        ],
    }
    if publication_timestamp is not None:
        response["publication_timestamp"] = publication_timestamp.isoformat()
    return response


@pytest.mark.parametrize(
    ("grid_product", "electricity_product"),
    [
        ("400D", "dynamic"),
        ("400F", "standard"),
        ("400ST", "standard"),
        ("400WP", "standard"),
        ("400B", "lighting"),
        ("400L", "business"),
        ("400LS", "business"),
        ("16L", "business"),
        ("16LS", "business"),
    ],
)
@pytest.mark.asyncio
async def test_grid_product_selects_matching_electricity_tariff(
    hass_time_zone, aioclient_mock, grid_product, electricity_product
):
    start = dt.datetime(2025, 12, 28, 12, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = start + dt.timedelta(minutes=15)
    params = {
        "start_timestamp": start.isoformat(timespec="seconds"),
        "end_timestamp": end.isoformat(timespec="seconds"),
    }
    for query in (
        {"tariff_name": f"grid_{grid_product}_inclFees"},
        {"tariff_name": f"electricity_{electricity_product}"},
        {"tariff_type": "feed_in"},
    ):
        component = (
            "feed_in" if "tariff_type" in query else query["tariff_name"].split("_")[0]
        )
        aioclient_mock.get(
            f"{API_BASE}{API_TARIFFS_PATH}",
            params={**params, **query},
            json=_component_response(start, end, component, 0.1, start),
        )

    api = EkzTariffsApi(async_get_clientsession(hass_time_zone))
    await api.fetch_tariffs(grid_product, None, start, end)

    assert aioclient_mock.call_count == 3


@pytest.mark.asyncio
async def test_public_fetches_components_and_applies_vat_to_all(
    hass_time_zone, aioclient_mock
):
    start = dt.datetime(2025, 12, 28, 12, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = start + dt.timedelta(minutes=15)
    published = start - dt.timedelta(hours=1)
    params = {
        "start_timestamp": start.isoformat(timespec="seconds"),
        "end_timestamp": end.isoformat(timespec="seconds"),
    }
    responses = (
        ("tariff_name", "grid_400D_inclFees", "grid", 0.20),
        ("tariff_name", "electricity_dynamic", "electricity", 0.10),
        ("tariff_name", "regional_fees_lt500MWh_ZH", "regional_fees", 0.05),
        ("tariff_type", "feed_in", "feed_in", 0.08),
    )
    for query_key, query_value, component, price in responses:
        aioclient_mock.get(
            f"{API_BASE}{API_TARIFFS_PATH}",
            params={**params, query_key: query_value},
            json=_component_response(start, end, component, price, published),
        )

    api = EkzTariffsApi(async_get_clientsession(hass_time_zone))
    slots = await api.fetch_tariffs(
        "400D",
        "lt500MWh_ZH",
        start,
        end,
        incl_vat=True,
    )

    assert aioclient_mock.call_count == 4
    assert len(slots) == 1
    slot = slots[0]
    assert slot.grid_chf_per_kwh == 0.2162
    assert slot.electricity_chf_per_kwh == 0.1081
    assert slot.regional_fees_chf_per_kwh == 0.0541
    assert slot.integrated_chf_per_kwh == 0.3243
    assert slot.price_chf_per_kwh == 0.3784
    assert slot.feed_in_chf_per_kwh == 0.08
    assert api.publication_timestamp == published


@pytest.mark.asyncio
async def test_public_without_region_omits_region_request(
    hass_time_zone, aioclient_mock
):
    start = dt.datetime(2025, 12, 28, 12, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = start + dt.timedelta(minutes=15)
    params = {
        "start_timestamp": start.isoformat(timespec="seconds"),
        "end_timestamp": end.isoformat(timespec="seconds"),
    }
    aioclient_mock.get(
        f"{API_BASE}{API_TARIFFS_PATH}",
        params={**params, "tariff_name": "grid_400D_inclFees"},
        json=_component_response(start, end, "grid", 0.20, start),
    )
    aioclient_mock.get(
        f"{API_BASE}{API_TARIFFS_PATH}",
        params={**params, "tariff_name": "electricity_dynamic"},
        json=_component_response(start, end, "electricity", 0.10, start),
    )
    aioclient_mock.get(
        f"{API_BASE}{API_TARIFFS_PATH}",
        params={**params, "tariff_type": "feed_in"},
        json=_component_response(start, end, "feed_in", 0.08, start),
    )

    api = EkzTariffsApi(async_get_clientsession(hass_time_zone))
    slots = await api.fetch_tariffs("400D", None, start, end)

    assert aioclient_mock.call_count == 3
    assert slots[0].price_chf_per_kwh == 0.30
    assert slots[0].integrated_chf_per_kwh == 0.30
    assert slots[0].regional_fees_chf_per_kwh == 0.0


@pytest.mark.asyncio
async def test_public_fetch_accepts_missing_publication_timestamp(
    hass_time_zone, aioclient_mock
):
    start = dt.datetime(2025, 12, 28, 12, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = start + dt.timedelta(minutes=15)
    params = {
        "start_timestamp": start.isoformat(timespec="seconds"),
        "end_timestamp": end.isoformat(timespec="seconds"),
    }
    for query, component in (
        ({"tariff_name": "grid_400D_inclFees"}, "grid"),
        ({"tariff_name": "electricity_dynamic"}, "electricity"),
        ({"tariff_type": "feed_in"}, "feed_in"),
    ):
        aioclient_mock.get(
            f"{API_BASE}{API_TARIFFS_PATH}",
            params={**params, **query},
            json=_component_response(start, end, component, 0.1, None),
        )

    api = EkzTariffsApi(async_get_clientsession(hass_time_zone))
    slots = await api.fetch_tariffs("400D", None, start, end)

    assert len(slots) == 1
    assert api.publication_timestamp is None


@pytest.mark.asyncio
async def test_oauth_fetches_all_components_in_one_request(
    hass_time_zone, aioclient_mock
):
    start = dt.datetime(2025, 12, 28, 12, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = start + dt.timedelta(minutes=15)
    published = start - dt.timedelta(hours=1)
    params = {
        "ems_instance_id": "ems-1",
        "start_timestamp": start.isoformat(timespec="seconds"),
        "end_timestamp": end.isoformat(timespec="seconds"),
    }
    aioclient_mock.get(
        f"{API_BASE}/customerTariffs",
        params=params,
        json={
            "publication_timestamp": published.isoformat(),
            "prices": [
                {
                    "start_timestamp": start.isoformat(),
                    "end_timestamp": end.isoformat(),
                    "grid": [{"unit": "CHF_kWh", "value": 0.20}],
                    "electricity": [{"unit": "CHF_kWh", "value": 0.10}],
                    "regional_fees": [{"unit": "CHF_kWh", "value": 0.05}],
                    "feed_in": [{"unit": "CHF_kWh", "value": 0.08}],
                }
            ],
        },
    )

    oauth_session = type(
        "OAuthSession",
        (),
        {
            "token": {"access_token": "token"},
            "async_ensure_token_valid": AsyncMock(),
        },
    )()
    api = EkzTariffsOAuthApi(oauth_session, async_get_clientsession(hass_time_zone))
    slots = await api.fetch_customer_tariffs("ems-1", start, end, incl_vat=True)

    assert aioclient_mock.call_count == 1
    assert len(slots) == 1
    assert slots[0].price_chf_per_kwh == 0.3784
    assert slots[0].integrated_chf_per_kwh == 0.3243
    assert slots[0].grid_chf_per_kwh == 0.2162
    assert slots[0].electricity_chf_per_kwh == 0.1081
    assert slots[0].regional_fees_chf_per_kwh == 0.0541
    assert slots[0].feed_in_chf_per_kwh == 0.08
    assert api.publication_timestamp == published
