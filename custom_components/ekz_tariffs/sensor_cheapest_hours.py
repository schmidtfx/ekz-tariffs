"""Binary sensor for detecting if current hour is in the cheapest/most expensive hours of the day."""

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


class EkzHoursQuantileSensor(BinarySensorEntity):
    """Binary sensor that indicates if the current hour is in a specific price quantile of today."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        tariff_name: str | None,
        coordinator,
        quantile: float = 0.25,
        mode: Literal["cheapest", "most_expensive"] = "cheapest",
    ) -> None:
        """Initialize the sensor.

        Args:
            quantile: The quantile threshold (0.0-1.0). E.g., 0.25 for cheapest/most expensive 25%
            mode: "cheapest" for low prices, "most_expensive" for high prices
        """
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._quantile = quantile
        self._mode = mode

        # Convert quantile to percentage for display
        percent = int(quantile * 100)
        mode_label = "cheapest" if mode == "cheapest" else "most_expensive"
        name_label = "Cheapest" if mode == "cheapest" else "Most expensive"

        self._attr_unique_id = f"{entry_id}_{mode_label}_{percent}_percent"
        self._attr_name = f"{name_label} {percent}% hours today"
        self._attr_icon = "mdi:cash-check" if mode == "cheapest" else "mdi:cash-remove"
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

    def _schedule_next_update(self) -> None:
        """Schedule next update at the start of the next hour or at midnight."""
        self._clear_boundary_timer()
        now = dt_util.now()

        # Schedule for the start of the next hour
        next_hour = (now + dt.timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )

        async def _on_hour_change(_now: dt.datetime) -> None:
            self.async_write_ha_state()
            self._schedule_next_update()

        self._unsub_boundary = async_track_point_in_time(
            self.hass, _on_hour_change, next_hour
        )

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - reschedule and update state."""
        self._schedule_next_update()
        self.async_write_ha_state()

    def _get_today_slots(
        self, slots: list[TariffSlot], now: dt.datetime
    ) -> list[TariffSlot]:
        """Get all slots for today (from midnight to next midnight)."""
        today_start = dt_util.start_of_local_day(now)
        today_end = today_start + dt.timedelta(days=1)

        return [
            slot
            for slot in slots
            if slot.start >= today_start and slot.start < today_end
        ]

    def _calculate_hourly_prices(self, slots: list[TariffSlot]) -> dict[int, float]:
        """Calculate the average price for each hour of the day (0-23)."""
        hourly_prices: dict[int, list[float]] = {}

        for slot in slots:
            hour = slot.start.hour
            if hour not in hourly_prices:
                hourly_prices[hour] = []
            hourly_prices[hour].append(slot.price_chf_per_kwh)

        # Average prices for each hour
        return {
            hour: sum(prices) / len(prices) for hour, prices in hourly_prices.items()
        }

    def _get_quantile_price(self, hourly_prices: dict[int, float]) -> float | None:
        """Calculate the quantile price from hourly prices."""
        if not hourly_prices:
            return None

        sorted_prices = sorted(hourly_prices.values())

        # Calculate the quantile index
        if self._mode == "cheapest":
            # For cheapest, use lower quantile
            index = int(len(sorted_prices) * self._quantile)
        else:
            # For most expensive, use upper quantile (reverse the threshold)
            index = int(len(sorted_prices) * (1.0 - self._quantile))

        # Ensure we don't go out of bounds
        index = max(0, min(index, len(sorted_prices) - 1))

        return sorted_prices[index]

    @property
    def is_on(self) -> bool | None:
        """Return True if current hour is in the target quantile of today."""
        slots: list[TariffSlot] = self._coordinator.data or []
        if not slots:
            return None

        now = dt_util.now()
        current_hour = now.hour

        # Get today's slots
        today_slots = self._get_today_slots(slots, now)
        if not today_slots:
            return None

        # Calculate hourly prices
        hourly_prices = self._calculate_hourly_prices(today_slots)
        if current_hour not in hourly_prices:
            return None

        # Get quantile price threshold
        threshold_price = self._get_quantile_price(hourly_prices)
        if threshold_price is None:
            return None

        # Check if current hour price meets the threshold
        current_price = hourly_prices[current_hour]
        if self._mode == "cheapest":
            return current_price <= threshold_price
        else:
            return current_price >= threshold_price

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        slots: list[TariffSlot] = self._coordinator.data or []
        now = dt_util.now()
        current_hour = now.hour
        percent = int(self._quantile * 100)

        attrs: dict[str, Any] = {
            "current_hour": current_hour,
            "quantile": self._quantile,
            "mode": self._mode,
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        if not slots:
            return attrs

        today_slots = self._get_today_slots(slots, now)
        if not today_slots:
            return attrs

        hourly_prices = self._calculate_hourly_prices(today_slots)
        threshold_price = self._get_quantile_price(hourly_prices)

        if current_hour in hourly_prices:
            attrs["current_hour_price"] = round(hourly_prices[current_hour], 6)

        if threshold_price is not None:
            attrs[f"threshold_price_{percent}th_percentile"] = round(threshold_price, 6)

        # Add all hourly prices for debugging
        attrs["hourly_prices"] = {
            hour: round(price, 6) for hour, price in sorted(hourly_prices.items())
        }

        # List hours that are in the target quantile
        if threshold_price is not None:
            if self._mode == "cheapest":
                matching_hours = [
                    hour
                    for hour, price in hourly_prices.items()
                    if price <= threshold_price
                ]
                attrs["cheap_hours"] = sorted(matching_hours)
            else:
                matching_hours = [
                    hour
                    for hour, price in hourly_prices.items()
                    if price >= threshold_price
                ]
                attrs["expensive_hours"] = sorted(matching_hours)

        return attrs
