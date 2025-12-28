from __future__ import annotations

import contextlib
import datetime as dt
from dataclasses import dataclass

from custom_components.ekz_tariffs.api import TariffSlot
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_TARIFF_START, EVENT_TYPE
from .coordinator import EkzTariffsCoordinator


@dataclass
class FusedEvent:
    start: dt.datetime
    end: dt.datetime
    price: float


def fuse_slots(slots: list[TariffSlot]) -> list[FusedEvent]:
    fused: list[FusedEvent] = []
    if not slots:
        return fused

    def norm(x: float) -> float:
        return round(x, 6)

    cur = FusedEvent(start=slots[0].start, end=slots[0].end, price=norm(slots[0].price_chf_per_kwh))
    for s in slots[1:]:
        p = norm(s.price_chf_per_kwh)
        if p == cur.price and s.start == cur.end:
            cur.end = s.end
        else:
            fused.append(cur)
            cur = FusedEvent(start=s.start, end=s.end, price=p)
    fused.append(cur)
    return fused


class EkzTariffsCalendar(CalendarEntity):
    _attr_name = "EKZ Tariffs"
    _attr_unique_id: str

    def __init__(self, hass: HomeAssistant, entry_id: str, tariff_name: str, coordinator: EkzTariffsCoordinator) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._tariff_name = tariff_name
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_calendar"

        self._events: list[CalendarEvent] = []
        self._fused: list[FusedEvent] = []
        self._unsubs: list[callable] = []

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.async_add_listener(self._handle_coordinator_update))
        self._handle_coordinator_update()

    def _clear_scheduled_callbacks(self) -> None:
        for unsub in self._unsubs:
            with contextlib.suppress(Exception):
                unsub()
        self._unsubs.clear()

    def _schedule_callbacks(self) -> None:
        self._clear_scheduled_callbacks()
        now = dt_util.now()

        for fe in self._fused:
            if fe.start <= now:
                continue

            def _make_cb(start: dt.datetime, end: dt.datetime, price: float):
                async def _cb(_now: dt.datetime) -> None:
                    self.hass.bus.async_fire(
                        EVENT_TYPE,
                        {
                            "type": EVENT_TARIFF_START,
                            "entry_id": self._entry_id,
                            "tariff_name": self._tariff_name,
                            "start": start.isoformat(),
                            "end": start.isoformat(),
                            "price_chf_per_kwh": price,
                        },
                    )
                return _cb

            unsub = async_track_point_in_time(self.hass, _make_cb(fe.start, fe.end, fe.price), fe.start)
            self._unsubs.append(unsub)

    def _handle_coordinator_update(self) -> None:
        slots: list[TariffSlot] = self._coordinator.data or []
        self._fused = fuse_slots(slots)

        events: list[CalendarEvent] = []
        for idx, fe in enumerate(self._fused):
            summary = f"EKZ {self._tariff_name}: {fe.price:.5f} CHF/kWh"
            desc = (
                f"Tariff: {self._tariff_name}\n"
                f"Price: {fe.price:.6f} CHF/kWh\n"
                f"From: {fe.start.isoformat()}\n"
                f"To: {fe.end.isoformat()}\n"
            )
            events.append(CalendarEvent(
                start=fe.start,
                end=fe.end,
                summary=summary,
                description=desc,
                uid=f"{self._entry_id}:{fe.start.isoformat()}:{idx}"
            ))

        self._events = events
        self._schedule_callbacks()
        self.async_write_ha_state()

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        for ev in self._events:
            if isinstance(ev.start, dt.datetime) and isinstance(ev.end, dt.datetime):
                if ev.start <= now < ev.end:
                    return ev
                if ev.start > now:
                    return ev
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: dt.datetime, end_date: dt.datetime) -> list[CalendarEvent]:
        # Follow HA calendar range semantics :contentReference[oaicite:4]{index=4}
        out: list[CalendarEvent] = []
        for ev in self._events:
            if not isinstance(ev.start, dt.datetime) or not isinstance(ev.end, dt.datetime):
                continue
            if ev.end <= start_date:
                continue
            if ev.start >= end_date:
                continue
            out.append(ev)
        out.sort(key=lambda e: e.start)
        return out


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entries: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entries(
        [EkzTariffsCalendar(hass, entry.entry_id, data["tariff_name"], data["coordinator"])],
        update_before_add=False,
    )
