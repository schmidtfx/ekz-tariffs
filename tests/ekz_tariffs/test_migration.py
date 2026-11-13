from __future__ import annotations

import pytest
from custom_components.ekz_tariffs import async_migrate_entry
from custom_components.ekz_tariffs.const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_PUBLIC,
    CONF_AUTH_TYPE,
    CONF_GRID_PRODUCT,
    CONF_INCLUDE_VAT,
    CONF_REGION,
    CONF_REGIONAL_FEE,
    CONF_TARIFF_NAME,
    DOMAIN,
)
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_migrate_legacy_400d_and_rename_total_price_history(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EKZ 400D",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_PUBLIC,
            CONF_TARIFF_NAME: "400D",
            CONF_REGIONAL_FEE: "regional_fees_lt500MWh_ZH",
            CONF_INCLUDE_VAT: True,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for old_suffix in ("current_price", "feed_in_price"):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_{old_suffix}",
            suggested_object_id=f"ekz_400d_{old_suffix}",
            config_entry=entry,
        )

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.data == {
        CONF_AUTH_TYPE: AUTH_TYPE_PUBLIC,
        CONF_GRID_PRODUCT: "400D",
        CONF_REGION: "lt500MWh_ZH",
        CONF_INCLUDE_VAT: True,
    }
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_integrated_complete"
        )
        == "sensor.ekz_400d_integrated_complete"
    )
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_feed_in")
        == "sensor.ekz_400d_feed_in"
    )
    assert (
        registry.async_get("sensor.ekz_400d_integrated_complete").translation_key
        == "integrated_complete"
    )


@pytest.mark.asyncio
async def test_migrate_other_public_product_without_electricity_prompt(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EKZ 400F",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_PUBLIC,
            CONF_TARIFF_NAME: "400F",
            CONF_REGIONAL_FEE: "none",
        },
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.data[CONF_GRID_PRODUCT] == "400F"
    assert entry.data[CONF_REGION] == "none"


@pytest.mark.asyncio
async def test_migration_only_supports_version_1(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EKZ 400D",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_PUBLIC,
            CONF_GRID_PRODUCT: "400D",
            CONF_REGION: "lt500MWh_ZH",
            CONF_INCLUDE_VAT: True,
        },
        version=2,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_current_price",
        suggested_object_id="ekz_400d_current_price",
        config_entry=entry,
    )

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_current_price"
        )
        == "sensor.ekz_400d_current_price"
    )


@pytest.mark.asyncio
async def test_migrate_oauth_entry_without_product_reconfiguration(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EKZ Customer Account",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_OAUTH,
            CONF_TARIFF_NAME: "400D",
            CONF_REGIONAL_FEE: False,
            CONF_INCLUDE_VAT: True,
        },
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.data == {
        CONF_AUTH_TYPE: AUTH_TYPE_OAUTH,
        CONF_INCLUDE_VAT: True,
    }
    assert CONF_GRID_PRODUCT not in entry.data
    assert CONF_REGION not in entry.data
