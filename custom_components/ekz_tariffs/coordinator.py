from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EkzTariffsApi, EkzTariffsOAuthApi, TariffSlot
from .const import DOMAIN
from .storage import slots_to_json

_LOGGER = logging.getLogger(__name__)


class EmsLinkStatusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch and share EMS link status data."""

    def __init__(self, hass: HomeAssistant, api, ems_instance_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ EMS Link Status",
            update_interval=None,
        )
        self._api = api
        self._ems_instance_id = ems_instance_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch EMS link status."""
        try:
            redirect_uri = (
                f"https://my.home-assistant.io/redirect/ekz-ems-linking?domain={DOMAIN}"
            )

            result = await self._api.check_ems_link_status(
                self._ems_instance_id, redirect_uri
            )
            return result

        except Exception as err:
            _LOGGER.error("Failed to fetch EMS link status: %s", err)
            # Return error dict instead of raising to keep entities available
            return {"error": True, "message": str(err)}


class EkzTariffsCoordinator(DataUpdateCoordinator[list[TariffSlot]]):
    """Coordinator for public API (requires tariff name)."""

    def __init__(
        self, hass: HomeAssistant, api: EkzTariffsApi, tariff_name: str, store: Store
    ):
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

            start = dt_util.start_of_local_day(
                dt_util.as_local(
                    dt_util.dt.datetime.combine(today, dt_util.dt.time.min)
                )
            )
            end = start + timedelta(days=2)
            slots = await self._api.fetch_tariffs(
                tariff_name=self._tariff_name,
                start=start,
                end=end,
            )
            await self._store.async_save({"slots": slots_to_json(slots)})
            return slots
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch EKZ tariffs: {err}") from err


class EkzTariffsOAuthCoordinator(DataUpdateCoordinator[list[TariffSlot]]):
    """Coordinator for OAuth API (customer-specific tariffs)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EkzTariffsOAuthApi,
        store: Store,
        ems_instance_id: str,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ Customer Tariffs",
            update_interval=None,
        )

        self._api = api
        self._store = store
        self._ems_instance_id = ems_instance_id

    async def _async_update_data(self) -> list[TariffSlot]:
        try:
            now = dt_util.now()
            today = dt_util.as_local(now).date()

            start = dt_util.start_of_local_day(
                dt_util.as_local(
                    dt_util.dt.datetime.combine(today, dt_util.dt.time.min)
                )
            )
            end = start + timedelta(days=2)
            slots = await self._api.fetch_customer_tariffs(
                ems_instance_id=self._ems_instance_id,
                start=start,
                end=end,
            )
            await self._store.async_save({"slots": slots_to_json(slots)})
            return slots
        except ClientResponseError as err:
            # Check if this is an EMS linking error (400 with ems_link in error type)
            if err.status == 400:
                _LOGGER.warning(
                    "EMS not linked yet for instance %s. "
                    "Please complete EMS linking process. Tariff data unavailable until linked.",
                    self._ems_instance_id,
                )
                # Return empty list instead of raising error - integration continues to work
                return []
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch EKZ customer tariffs: {err}") from err
