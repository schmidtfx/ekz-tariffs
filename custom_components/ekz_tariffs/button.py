"""Button platform for EKZ Tariffs."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUTH_TYPE_OAUTH, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EkzRefreshTariffsButton(ButtonEntity):
    """Button to refresh tariff data."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator) -> None:
        """Initialize the button."""
        self.hass = hass
        self._entry_id = entry_id
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_refresh_tariffs"
        self._attr_name = "Refresh tariffs"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Refresh tariffs button pressed")
        await self._coordinator.async_request_refresh()


class EkzCheckEmsLinkStatusButton(ButtonEntity):
    """Button to check EMS link status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:link-variant"

    def __init__(self, hass: HomeAssistant, entry_id: str, ems_coordinator) -> None:
        """Initialize the button."""
        self.hass = hass
        self._entry_id = entry_id
        self._ems_coordinator = ems_coordinator
        self._attr_unique_id = f"{entry_id}_check_ems_link_status"
        self._attr_name = "Check EMS link status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Check EMS link status button pressed")
        await self._ems_coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EKZ Tariffs button entities."""
    data = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EkzRefreshTariffsButton(hass, entry.entry_id, data["coordinator"]),
    ]

    # Add EMS link status check button for OAuth configurations
    if data.get("auth_type") == AUTH_TYPE_OAUTH:
        ems_coordinator = data.get("ems_coordinator")
        if ems_coordinator:
            entities.append(
                EkzCheckEmsLinkStatusButton(hass, entry.entry_id, ems_coordinator)
            )

    async_add_entities(entities)
