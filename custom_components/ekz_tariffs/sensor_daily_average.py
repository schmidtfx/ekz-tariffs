import contextlib
import datetime as dt
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import TariffSlot
from .const import DOMAIN
from .coordinator import EkzTariffsCoordinator
from .statistics import daily_stats
from .utils import next_midnight


class _EkzDailyAverageSensor(SensorEntity):
    _attr_native_unit_of_measurement = "CHF/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_icon = "mdi:cash-100"

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        tariff_name: str | None,
        coordinator: EkzTariffsCoordinator,
        day_offset: int,
        name: str,
        unique_suffix: str,
        enabled_default: bool = True,
    ):
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._day_offset = day_offset
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._attr_entity_registry_enabled_default = enabled_default
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
        stats = daily_stats(slots, day)
        if stats["avg"] is None:
            return None
        return round(stats["avg"], 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slots: list[TariffSlot] = self._coordinator.data or []
        day = dt_util.as_local(dt_util.now()).date() + dt.timedelta(
            days=self._day_offset
        )
        stats = daily_stats(slots, day)

        attrs: dict[str, Any] = {
            "day": day.isoformat(),
            "slots_count": stats["slots_count"],
            "covered_minutes": stats["covered_minutes"],
        }

        if self._tariff_name:
            attrs["tariff_name"] = self._tariff_name

        attrs["min_price_chf_per_kwh"] = (
            round(stats["min"], 6) if stats["min"] is not None else None
        )
        attrs["max_price_chf_per_kwh"] = (
            round(stats["max"], 6) if stats["max"] is not None else None
        )
        attrs["median_price_chf_per_kwh"] = (
            round(stats["median"], 6) if stats["median"] is not None else None
        )
        attrs["q25_price_chf_per_kwh"] = (
            round(stats["q25"], 6) if stats["q25"] is not None else None
        )
        attrs["q75_price_chf_per_kwh"] = (
            round(stats["q75"], 6) if stats["q75"] is not None else None
        )

        return attrs


class EkzAverageTodaySensor(_EkzDailyAverageSensor):
    def __init__(self, hass, entry_id, tariff_name, coordinator):
        super().__init__(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset=0,
            name="Average price today",
            unique_suffix="avg_today",
        )


class EkzAverageTomorrowSensor(_EkzDailyAverageSensor):
    def __init__(self, hass, entry_id, tariff_name, coordinator):
        super().__init__(
            hass,
            entry_id,
            tariff_name,
            coordinator,
            day_offset=1,
            name="Average price tomorrow",
            unique_suffix="avg_tomorrow",
            enabled_default=False,
        )
