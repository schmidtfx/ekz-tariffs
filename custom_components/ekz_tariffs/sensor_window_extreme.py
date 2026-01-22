import contextlib
import datetime as dt
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import TariffSlot
from .const import DOMAIN
from .coordinator import EkzTariffsCoordinator
from .statistics import bucket_prices, rolling_window_extreme
from .utils import next_midnight


class EkzWindowExtremeSensor(SensorEntity):
    _attr_native_unit_of_measurement = "CHF/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        tariff_name: str | None,
        coordinator: EkzTariffsCoordinator,
        day_offset: int,
        window_minutes: int,
        mode: str,
        name: str,
        unique_suffix: str,
    ):
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._day_offset = day_offset
        self._window_minutes = window_minutes
        self._mode = mode
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._unsub_midnight = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self):
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_update))
        self._schedule_midnight_update()
        self._handle_update()

    def _schedule_midnight_update(self):
        if self._unsub_midnight:
            with contextlib.suppress(Exception):
                self._unsub_midnight()
            self._unsub_midnight = None

        when = next_midnight(dt_util.now())

        async def _on_midnight(_now: dt.datetime):
            self.async_write_ha_state()
            self._schedule_midnight_update()

        self._unsub_midnight = async_track_point_in_time(self.hass, _on_midnight, when)

    def _handle_update(self):
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        slots: list[TariffSlot] = self._coordinator.data or []
        day = dt_util.as_local(dt_util.now()).date() + dt.timedelta(
            days=self._day_offset
        )

        prices, day_start = bucket_prices(slots, day)
        res = rolling_window_extreme(
            prices, day_start, self._window_minutes, self._mode
        )
        if res is None:
            return None
        return round(res.avg, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        day = dt_util.as_local(dt_util.now()).date() + dt.timedelta(
            days=self._day_offset
        )

        prices, day_start = bucket_prices(slots, day)
        res = rolling_window_extreme(
            prices, day_start, self._window_minutes, self._mode
        )

        attrs: dict[str, Any] = {
            "date": day.isoformat(),
            "window_minutes": self._window_minutes,
            "mode": self._mode,
            "missing_buckets": prices.count(None),
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        if res is not None:
            attrs["window_start"] = res.start.isoformat()
            attrs["window_end"] = res.end.isoformat()
        else:
            attrs["window_start"] = None
            attrs["window_end"] = None

        return attrs

    @property
    def icon(self):
        if self._mode == "min":
            return "mdi:arrow-bottom-right"
        return "mdi:arrow-top-right"
