from __future__ import annotations

import datetime as dt
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import EkzTariffsApi, EkzTariffsOAuthApi
from .const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_PUBLIC,
    CONF_AUTH_TYPE,
    CONF_EMS_INSTANCE_ID,
    CONF_TARIFF_NAME,
    DEFAULT_TARIFF_NAME,
    DOMAIN,
    FETCH_HOUR,
    FETCH_MINUTE,
    PLATFORMS,
    SERVICE_CHECK_EMS_LINK_STATUS,
    SERVICE_REFRESH,
)
from .coordinator import (
    EkzTariffsCoordinator,
    EkzTariffsOAuthCoordinator,
    EmsLinkStatusCoordinator,
)
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
        # OAuth setup
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
        coordinator = EkzTariffsOAuthCoordinator(hass, api, store, ems_instance_id)

        # Create EMS link status coordinator
        ems_coordinator = EmsLinkStatusCoordinator(hass, api, ems_instance_id)

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
            "tariff_name": None,  # For OAuth, don't populate tariff_name
            "ems_instance_id": ems_instance_id,
            "device_id": device.id,
            "api": api,  # Pass API for EMS link status sensor
            "ems_coordinator": ems_coordinator,  # Share coordinator with sensors
        }
    else:
        # Public API setup
        tariff_name = entry.data.get(CONF_TARIFF_NAME, DEFAULT_TARIFF_NAME)
        session = async_get_clientsession(hass)
        api = EkzTariffsApi(session)
        coordinator = EkzTariffsCoordinator(hass, api, tariff_name, store)

        device_name = f"EKZ Tariff {tariff_name}"
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="EKZ",
            model=f"Dynamic Tariff ({tariff_name})",
            configuration_url="https://www.ekz.ch/",
        )

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "coordinator": coordinator,
            "tariff_name": tariff_name,
            "auth_type": AUTH_TYPE_PUBLIC,
            "device_id": device.id,
        }

    # Load saved data
    saved = await store.async_load()
    if saved and "slots" in saved:
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
