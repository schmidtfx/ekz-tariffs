from __future__ import annotations

import contextlib
import datetime as dt
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import TariffSlot
from .const import DOMAIN


def _find_current_slot(slots: list[TariffSlot], now: dt.datetime) -> TariffSlot | None:
    for s in slots:
        if s.start <= now < s.end:
            return s
    return None


def _find_next_boundary(slots: list[TariffSlot], now: dt.datetime) -> dt.datetime | None:
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
    _attr_name = "Current price"
    _attr_native_unit_of_measurement = "CHF/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry_id: str, tariff_name: str, coordinator) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_current_price"
        self._unsub_boundary: Any | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_coordinator_update))
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

        next_boundary = _find_next_boundary(slots, now)
        if not next_boundary or next_boundary <= now:
            return

        async def _on_boundary(_now: dt.datetime) -> None:
            # Recompute native_value/attributes and then schedule the *next* boundary.
            self.async_write_ha_state()
            self._schedule_next_boundary_update()

        self._unsub_boundary = async_track_point_in_time(self.hass, _on_boundary, next_boundary)

    def _handle_coordinator_update(self) -> None:
        # Tariff schedule changed (daily refresh) -> reschedule boundary updates
        self._schedule_next_boundary_update()
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()
        cur = _find_current_slot(slots, now)
        if not cur:
            return None
        # avoid float noise; keep sensor stable
        return round(cur.price_chf_per_kwh, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()

        cur = _find_current_slot(slots, now)
        next_boundary = _find_next_boundary(slots, now)

        attrs: dict[str, Any] = {
            "tariff_name": self._tariff_name,
            "schedule_date": dt_util.as_local(now).date().isoformat(),
            "next_change": next_boundary.isoformat() if next_boundary else None,
        }

        if cur:
            attrs.update({
                "slot_start": cur.start.isoformat(),
                "slot_end": cur.end.isoformat(),
            })

        return attrs


class EkzNextChangeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Next change"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, hass: HomeAssistant, entry_id: str, tariff_name: str, coordinator) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_next_change"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))
        self._handle_update()

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> dt.datetime | None:
        slots: list[TariffSlot] = self._coordinator.data or []
        return _find_next_boundary(slots, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()
        cur = _find_current_slot(slots, now)
        return {
            "tariff_name": self._tariff_name,
            "slot_start": cur.start.isoformat() if cur else None,
            "slot_end": cur.end.isoformat() if cur else None,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EkzCurrentPriceSensor(hass, entry.entry_id, data["tariff_name"], data["coordinator"]),
            EkzNextChangeSensor(hass, entry.entry_id, data["tariff_name"], data["coordinator"])
        ],
        update_before_add=False,
    )
