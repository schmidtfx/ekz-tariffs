from __future__ import annotations

import datetime as dt
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .api import EkzTariffsApi, EkzTariffsOAuthApi
from .const import (
    AUTH_IMPL_PUBLIC_CLIENT,
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_PUBLIC,
    CONF_AUTH_TYPE,
    CONF_CLIENT_ID,
    CONF_EMS_INSTANCE_ID,
    CONF_GRID_PRODUCT,
    CONF_INCLUDE_VAT,
    CONF_REGION,
    CONF_REGIONAL_FEE,
    CONF_TARIFF_NAME,
    DEFAULT_TARIFF_NAME,
    DOMAIN,
    ELECTRICITY_PRODUCT_BY_GRID_PRODUCT,
    FETCH_HOUR,
    FETCH_MINUTE,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    PLATFORMS,
    REGION_CHOICES,
    SERVICE_CHECK_EMS_LINK_STATUS,
    SERVICE_REFRESH,
)
from .coordinator import (
    EkzTariffsCoordinator,
    EkzTariffsOAuthCoordinator,
    EmsLinkStatusCoordinator,
)
from .oauth_impl import EKZOAuth2Implementation
from .storage import make_store, slots_from_json

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EKZ Tariffs from a config entry."""
    auth_type = entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PUBLIC)
    store = make_store(hass, entry.entry_id)

    # Register device
    device_registry = dr.async_get(hass)

    # Setup based on authentication type
    if auth_type == AUTH_TYPE_OAUTH:
        # OAuth setup — public-client entries (PKCE, no client_secret) don't
        # go through Application Credentials, so their implementation must be
        # re-registered here on each startup from the stored client_id.
        public_client_id = entry.data.get(CONF_CLIENT_ID)
        if public_client_id:
            config_entry_oauth2_flow.async_register_implementation(
                hass,
                DOMAIN,
                EKZOAuth2Implementation(
                    hass,
                    AUTH_IMPL_PUBLIC_CLIENT,
                    public_client_id,
                    "",
                    OAUTH2_AUTHORIZE,
                    OAUTH2_TOKEN,
                ),
            )

        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )

        # Get the EMS instance ID from config entry
        ems_instance_id = entry.data.get(CONF_EMS_INSTANCE_ID)
        if not ems_instance_id:
            _LOGGER.error("No EMS instance ID found in config entry")
            return False

        session = async_get_clientsession(hass)
        api = EkzTariffsOAuthApi(oauth_session, session)
        include_vat = entry.data.get(CONF_INCLUDE_VAT, False)
        coordinator = EkzTariffsOAuthCoordinator(
            hass,
            entry,
            api,
            store,
            ems_instance_id,
            incl_vat=include_vat,
        )

        # Create EMS link status coordinator
        ems_coordinator = EmsLinkStatusCoordinator(hass, entry, api, ems_instance_id)

        # Add listener to refresh tariff coordinator when EMS linking completes
        def _handle_ems_link_change() -> None:
            """Trigger tariff refresh when EMS link status changes."""
            if ems_coordinator.data:
                previous_status = getattr(
                    _handle_ems_link_change, "_previous_status", None
                )
                current_status = ems_coordinator.data.get("link_status")

                # If status changed from link_required to something else, refresh tariffs
                if (
                    previous_status == "link_required"
                    and current_status != "link_required"
                ):
                    _LOGGER.info("EMS linking completed, refreshing tariff data")
                    hass.async_create_task(coordinator.async_request_refresh())

                _handle_ems_link_change._previous_status = current_status

        ems_coordinator.async_add_listener(_handle_ems_link_change)

        device_name = "EKZ Customer Tariff"
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="EKZ",
            model="Dynamic Tariff (OAuth)",
            serial_number=ems_instance_id,
            configuration_url="https://www.ekz.ch/",
        )

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "coordinator": coordinator,
            "auth_type": AUTH_TYPE_OAUTH,
            "oauth_session": oauth_session,
            "tariff_name": None,
            "price_tariff_names": {
                "electricity": None,
                "grid": None,
                "regional_fees": None,
                "integrated": None,
                "integrated_complete": None,
                "feed_in": None,
            },
            "ems_instance_id": ems_instance_id,
            "device_id": device.id,
            "api": api,  # Pass API for EMS link status sensor
            "ems_coordinator": ems_coordinator,  # Share coordinator with sensors
        }
    else:
        # Public API setup
        grid_product = entry.data.get(CONF_GRID_PRODUCT, DEFAULT_TARIFF_NAME)
        electricity_product = ELECTRICITY_PRODUCT_BY_GRID_PRODUCT[grid_product]
        region = entry.data.get(CONF_REGION, REGION_CHOICES[0])
        configured_region = region in REGION_CHOICES
        include_vat = entry.data.get(CONF_INCLUDE_VAT, False)
        session = async_get_clientsession(hass)
        api = EkzTariffsApi(session)
        coordinator = EkzTariffsCoordinator(
            hass,
            entry,
            api,
            grid_product,
            region if configured_region else None,
            store,
            incl_vat=include_vat,
        )

        device_name = f"EKZ Tariff {grid_product}"
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="EKZ",
            model=f"Dynamic Tariff ({grid_product})",
            configuration_url="https://www.ekz.ch/",
        )

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "coordinator": coordinator,
            "tariff_name": grid_product,
            "price_tariff_names": {
                "electricity": f"electricity_{electricity_product}",
                "grid": f"grid_{grid_product}_inclFees",
                "regional_fees": (
                    f"regional_fees_{region}" if configured_region else None
                ),
                "integrated": f"integrated_{grid_product}",
                "integrated_complete": grid_product,
                "feed_in": "feed_in",
            },
            "auth_type": AUTH_TYPE_PUBLIC,
            "device_id": device.id,
        }

    # Load saved data
    saved = await store.async_load()
    if saved and "slots" in saved:
        # Restore the fetch time first so the initial state already carries a
        # correct publication_timestamp. Absent on caches written before 0.8.0.
        fetched_at = saved.get("fetched_at")
        if fetched_at:
            coordinator.last_fetched = dt_util.parse_datetime(fetched_at)
        publication_timestamp = saved.get("publication_timestamp")
        if publication_timestamp:
            coordinator.publication_timestamp = dt_util.parse_datetime(
                publication_timestamp
            )
        else:
            coordinator.publication_timestamp = coordinator.last_fetched
        coordinator.async_set_updated_data(slots_from_json(saved["slots"]))

    await coordinator.async_config_entry_first_refresh()

    # Setup scheduled refresh
    async def _scheduled_refresh(_now: dt.datetime) -> None:
        _LOGGER.debug("Scheduled refresh triggered")
        await coordinator.async_request_refresh()

    unsub = async_track_time_change(
        hass,
        _scheduled_refresh,
        hour=FETCH_HOUR,
        minute=FETCH_MINUTE,
        second=0,
    )
    entry.async_on_unload(unsub)

    # Register refresh service
    async def _handle_refresh(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _handle_refresh,
    )

    # Register check EMS link status service (only for OAuth)
    if auth_type == AUTH_TYPE_OAUTH:

        async def _handle_check_ems_link_status(call: ServiceCall) -> None:
            """Check EMS link status and refresh coordinator."""
            _LOGGER.info("Checking EMS link status")
            await ems_coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_CHECK_EMS_LINK_STATUS,
            _handle_check_ems_link_status,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate configuration and entity IDs from prior releases."""
    if entry.version != 1:
        return False

    data = dict(entry.data)
    auth_type = data.get(CONF_AUTH_TYPE, AUTH_TYPE_PUBLIC)
    grid_product = data.pop(CONF_TARIFF_NAME, DEFAULT_TARIFF_NAME)
    legacy_region = data.pop(CONF_REGIONAL_FEE, None)
    if auth_type == AUTH_TYPE_PUBLIC:
        data.setdefault(CONF_GRID_PRODUCT, grid_product)
        if isinstance(legacy_region, str) and legacy_region != "none":
            data[CONF_REGION] = legacy_region.removeprefix("regional_fees_")
        else:
            data[CONF_REGION] = "none"

    registry = er.async_get(hass)
    for old_suffix, new_suffix in (
        ("current_price", "integrated_complete"),
        ("feed_in_price", "feed_in"),
    ):
        old_unique_id = f"{entry.entry_id}_{old_suffix}"
        old_entity_id = registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        if old_entity_id is None:
            continue
        new_entity_id = old_entity_id
        legacy_entity_suffix = f"_{old_suffix}"
        if old_entity_id.endswith(legacy_entity_suffix):
            new_entity_id = (
                f"{old_entity_id[: -len(legacy_entity_suffix)]}_{new_suffix}"
            )
        registry.async_update_entity(
            old_entity_id,
            new_unique_id=f"{entry.entry_id}_{new_suffix}",
            new_entity_id=new_entity_id,
            translation_key=new_suffix,
        )

    hass.config_entries.async_update_entry(
        entry,
        data=data,
        version=2,
    )
    return True
