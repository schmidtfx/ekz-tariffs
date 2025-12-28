from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)
from homeassistant.util import dt as dt_util

from custom_components.ekz_tariffs.storage import slots_to_json

from .api import EkzTariffsApi, TariffSlot

_LOGGER = logging.getLogger(__name__)

class EkzTariffsCoordinator(DataUpdateCoordinator[list[TariffSlot]]):
    def __init__(self, hass: HomeAssistant, api: EkzTariffsApi, tariff_name: str, store: Store):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ Tariffs",
            update_interval=None,
        )

        self._api = api
        self._tariff_name = tariff_name
        self._store = store

    async def _async_update_data(self) -> list[TariffSlot]:
        try:
            now = dt_util.now()
            today = dt_util.as_local(now).date()

            start = dt_util.start_of_local_day(dt_util.as_local(dt_util.dt.datetime.combine(today, dt_util.dt.time.min)))
            end = start + timedelta(days=2)
            slots =  await self._api.fetch_tariffs(
                tariff_name=self._tariff_name,
                start=start,
                end=end,
            )
            await self._store.async_save({"slots": slots_to_json(slots)})
            return slots
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch EKZ tariffs: {err}") from err

