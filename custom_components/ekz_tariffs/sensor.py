from __future__ import annotations

import contextlib
import datetime as dt
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import TariffSlot
from .const import AUTH_TYPE_OAUTH, DOMAIN
from .coordinator import EmsLinkStatusCoordinator
from .sensor_daily_average import EkzAverageTodaySensor, EkzAverageTomorrowSensor
from .sensor_window_extreme import EkzWindowExtremeSensor
from .utils import FusedEvent, fuse_slots


def _find_current_slot(slots: list[FusedEvent], now: dt.datetime) -> FusedEvent | None:
    for s in slots:
        if s.start <= now < s.end:
            return s
    return None


def _find_next_boundary(
    slots: list[FusedEvent], now: dt.datetime
) -> dt.datetime | None:
    """
    Next moment when the price can change:
    - if currently in a slot: its end
    - else: the next slot start after now
    """
    cur = _find_current_slot(slots, now)
    if cur:
        return cur.end

    for s in slots:
        if s.start > now:
            return s.start
    return None


class EkzCurrentPriceSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "CHF/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash-100"

    def __init__(
        self, hass: HomeAssistant, entry_id: str, tariff_name: str | None, coordinator
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_current_price"
        self._attr_name = "Current price"
        self._unsub_boundary: Any | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()

    def _clear_boundary_timer(self) -> None:
        if self._unsub_boundary:
            with contextlib.suppress(Exception):
                self._unsub_boundary()
            self._unsub_boundary = None

    def _schedule_next_boundary_update(self) -> None:
        self._clear_boundary_timer()
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()

        fused_slots = fuse_slots(slots)
        next_boundary = _find_next_boundary(fused_slots, now)
        if not next_boundary or next_boundary <= now:
            return

        async def _on_boundary(_now: dt.datetime) -> None:
            # Recompute native_value/attributes and then schedule the *next* boundary.
            self.async_write_ha_state()
            self._schedule_next_boundary_update()

        self._unsub_boundary = async_track_point_in_time(
            self.hass, _on_boundary, next_boundary
        )

    def _handle_coordinator_update(self) -> None:
        # Tariff schedule changed (daily refresh) -> reschedule boundary updates
        self._schedule_next_boundary_update()
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()
        fused_slots = fuse_slots(slots)
        cur = _find_current_slot(fused_slots, now)
        if not cur:
            return None
        # avoid float noise; keep sensor stable
        return round(cur.price, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()

        fused_slots = fuse_slots(slots)
        cur = _find_current_slot(fused_slots, now)
        next_boundary = _find_next_boundary(fused_slots, now)

        attrs: dict[str, Any] = {
            "schedule_date": dt_util.as_local(now).date().isoformat(),
            "next_change": next_boundary.isoformat() if next_boundary else None,
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        if cur:
            attrs.update(
                {
                    "slot_start": cur.start.isoformat(),
                    "slot_end": cur.end.isoformat(),
                }
            )

        return attrs


class EkzNextChangeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, hass: HomeAssistant, entry_id: str, tariff_name: str | None, coordinator
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._attr_name = "Next change"
        self._attr_unique_id = f"{entry_id}_next_change"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))
        self._handle_update()

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> dt.datetime | None:
        slots: list[TariffSlot] = self._coordinator.data or []
        fused_slots = fuse_slots(slots)
        return _find_next_boundary(fused_slots, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()
        fused_slots = fuse_slots(slots)
        cur = _find_current_slot(fused_slots, now)
        attrs = {
            "slot_start": cur.start.isoformat() if cur else None,
            "slot_end": cur.end.isoformat() if cur else None,
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        return attrs


class EkzEmsLinkStatusSensor(BinarySensorEntity):
    """Binary sensor showing EMS linking status for OAuth configurations."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, hass: HomeAssistant, entry_id: str, coordinator: EmsLinkStatusCoordinator
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_ems_link_status"
        self._attr_name = "EMS link status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Fetch initial status when added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        await self._coordinator.async_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch EMS link status from coordinator."""
        await self._coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool | None:
        """Return true if EMS is linked."""
        if not self._coordinator.data:
            return None

        result = self._coordinator.data
        return result.get("error") or result.get("link_status") == "link_required"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "ems_instance_id": self._coordinator._ems_instance_id,
        }

        if self._coordinator.data:
            result = self._coordinator.data

            if result.get("link_status") == "link_required":
                linking_url = result.get("linking_process_redirect_uri")
                if linking_url:
                    attrs["linking_url"] = linking_url

            if result.get("error"):
                attrs["last_error"] = result.get("message", "Unknown error")

        return attrs


class EkzEmsLinkingUrlSensor(SensorEntity):
    """Sensor showing the EMS linking status with URL in attributes."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:link"

    def __init__(
        self, hass: HomeAssistant, entry_id: str, coordinator: EmsLinkStatusCoordinator
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_ems_linking_url"
        self._attr_name = "EMS linking URL"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Fetch initial URL when added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        await self._coordinator.async_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch EMS linking URL from coordinator."""
        await self._coordinator.async_request_refresh()

    @property
    def native_value(self) -> str | None:
        """Return link status."""
        if not self._coordinator.data:
            return None

        result = self._coordinator.data
        if result.get("link_status") == "link_required":
            return "Link required"

        return "Linked"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the linking URL as an attribute."""
        attrs = {}

        if self._coordinator.data:
            result = self._coordinator.data

            if result.get("link_status") == "link_required":
                linking_url = result.get("linking_process_redirect_uri")
                if linking_url:
                    attrs["linking_url"] = linking_url

        return attrs

    @property
    def available(self) -> bool:
        """Return True only if there's a linking URL to display."""
        if not self._coordinator.data:
            return False

        result = self._coordinator.data
        return result.get("link_status") == "link_required"


def _mk_windows(hass, entry_id, tariff_name, coordinator, day_offset: int, suffix: str):
    label = "today" if day_offset == 0 else "tomorrow"
    return [
        EkzWindowExtremeSensor(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset,
            window_minutes=240,
            mode="min",
            name=f"Lowest 4h window {label}",
            unique_suffix=f"lowest_4h_{suffix}",
        ),
        EkzWindowExtremeSensor(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset,
            window_minutes=120,
            mode="min",
            name=f"Lowest 2h window {label}",
            unique_suffix=f"lowest_2h_{suffix}",
        ),
        EkzWindowExtremeSensor(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset,
            window_minutes=240,
            mode="max",
            name=f"Highest 4h window {label}",
            unique_suffix=f"highest_4h_{suffix}",
        ),
        EkzWindowExtremeSensor(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset,
            window_minutes=120,
            mode="max",
            name=f"Highest 2h window {label}",
            unique_suffix=f"highest_2h_{suffix}",
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EkzCurrentPriceSensor(
            hass, entry.entry_id, data["tariff_name"], data["coordinator"]
        ),
        EkzNextChangeSensor(
            hass, entry.entry_id, data["tariff_name"], data["coordinator"]
        ),
        EkzAverageTodaySensor(
            hass, entry.entry_id, data["tariff_name"], data["coordinator"]
        ),
        EkzAverageTomorrowSensor(
            hass, entry.entry_id, data["tariff_name"], data["coordinator"]
        ),
    ]

    entities += _mk_windows(
        hass,
        entry.entry_id,
        data["tariff_name"],
        data["coordinator"],
        day_offset=0,
        suffix="today",
    )
    entities += _mk_windows(
        hass,
        entry.entry_id,
        data["tariff_name"],
        data["coordinator"],
        day_offset=1,
        suffix="tomorrow",
    )

    # Add EMS link status and linking URL sensors for OAuth configurations
    if data.get("auth_type") == AUTH_TYPE_OAUTH:
        # Use shared coordinator from hass.data
        ems_coordinator = data.get("ems_coordinator")

        if ems_coordinator:
            entities.extend(
                [
                    EkzEmsLinkStatusSensor(hass, entry.entry_id, ems_coordinator),
                    EkzEmsLinkingUrlSensor(hass, entry.entry_id, ems_coordinator),
                ]
            )

    async_add_entities(entities, update_before_add=False)
