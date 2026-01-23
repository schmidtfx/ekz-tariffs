"""Binary sensor for detecting if current time is in the cheapest/most expensive consecutive hour window."""

from __future__ import annotations

import contextlib
import datetime as dt
from typing import Any, Literal

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import TariffSlot
from .const import DOMAIN
from .statistics import bucket_prices, rolling_window_extreme
from .utils import next_midnight


class EkzInConsecutiveWindowSensor(BinarySensorEntity):
    """Binary sensor that indicates if current time is in the cheapest/most expensive consecutive window."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        tariff_name: str | None,
        coordinator,
        window_hours: int = 2,
        mode: Literal["cheapest", "most_expensive"] = "cheapest",
    ) -> None:
        """Initialize the sensor.

        Args:
            window_hours: Number of consecutive hours (e.g., 2 for 2-hour window, 4 for 4-hour window)
            mode: "cheapest" for lowest prices, "most_expensive" for highest prices
        """
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._window_hours = window_hours
        self._window_minutes = window_hours * 60
        self._mode = mode
        self._stat_mode = "min" if mode == "cheapest" else "max"

        # Create unique IDs and names
        mode_label = "cheapest" if mode == "cheapest" else "most_expensive"
        name_label = "Cheapest" if mode == "cheapest" else "Most expensive"

        self._attr_unique_id = f"{entry_id}_in_{mode_label}_{window_hours}h_window"
        self._attr_name = f"In {name_label} {window_hours}h window today"
        self._attr_icon = (
            "mdi:clock-check-outline"
            if mode == "cheapest"
            else "mdi:clock-alert-outline"
        )
        self._unsub_update: Any | None = None
        self._unsub_midnight: Any | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._schedule_midnight_update()
        self._schedule_next_boundary_update()
        self._handle_coordinator_update()

    def _clear_boundary_timer(self) -> None:
        if self._unsub_update:
            with contextlib.suppress(Exception):
                self._unsub_update()
            self._unsub_update = None

    def _clear_midnight_timer(self) -> None:
        if self._unsub_midnight:
            with contextlib.suppress(Exception):
                self._unsub_midnight()
            self._unsub_midnight = None

    def _schedule_midnight_update(self) -> None:
        """Schedule update at midnight when the window changes."""
        self._clear_midnight_timer()
        when = next_midnight(dt_util.now())

        async def _on_midnight(_now: dt.datetime) -> None:
            self.async_write_ha_state()
            self._schedule_midnight_update()
            self._schedule_next_boundary_update()

        self._unsub_midnight = async_track_point_in_time(self.hass, _on_midnight, when)

    def _schedule_next_boundary_update(self) -> None:
        """Schedule update at window boundaries."""
        self._clear_boundary_timer()

        now = dt_util.now()
        window_result = self._get_window_result()

        if window_result is None:
            return

        # Schedule at window start or end, whichever is next
        next_boundary = None
        if now < window_result.start:
            next_boundary = window_result.start
        elif now < window_result.end:
            next_boundary = window_result.end

        if next_boundary and next_boundary > now:

            async def _on_boundary(_now: dt.datetime) -> None:
                self.async_write_ha_state()
                self._schedule_next_boundary_update()

            self._unsub_update = async_track_point_in_time(
                self.hass, _on_boundary, next_boundary
            )

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - reschedule and update state."""
        self._schedule_next_boundary_update()
        self.async_write_ha_state()

    def _get_window_result(self):
        """Get the window result for today."""
        slots: list[TariffSlot] = self._coordinator.data or []
        if not slots:
            return None

        day = dt_util.as_local(dt_util.now()).date()
        prices, day_start = bucket_prices(slots, day)
        return rolling_window_extreme(
            prices, day_start, self._window_minutes, self._stat_mode
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if current time is in the target consecutive window."""
        window_result = self._get_window_result()
        if window_result is None:
            return None

        now = dt_util.now()
        return window_result.start <= now < window_result.end

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        now = dt_util.now()
        day = dt_util.as_local(now).date()

        attrs: dict[str, Any] = {
            "window_hours": self._window_hours,
            "mode": self._mode,
            "date": day.isoformat(),
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        window_result = self._get_window_result()
        if window_result is not None:
            attrs["window_start"] = window_result.start.isoformat()
            attrs["window_end"] = window_result.end.isoformat()
            attrs["window_average_price"] = round(window_result.avg, 6)

            # Check if we're currently in the window
            in_window = window_result.start <= now < window_result.end
            attrs["in_window"] = in_window
        else:
            attrs["window_start"] = None
            attrs["window_end"] = None
            attrs["window_average_price"] = None
            attrs["in_window"] = None

        return attrs
