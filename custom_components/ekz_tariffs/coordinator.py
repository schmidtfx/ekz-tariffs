from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from homeassistant.config_entries import ConfigEntry
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api,
        ems_instance_id: str,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ EMS Link Status",
            update_interval=None,
            config_entry=config_entry,
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
    """Coordinator for the public API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: EkzTariffsApi,
        grid_product: str,
        region: str | None,
        store: Store,
        incl_vat: bool = False,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ Tariffs",
            update_interval=None,
            config_entry=config_entry,
        )

        self._api = api
        self._grid_product = grid_product
        self._region = region
        self._store = store
        self._incl_vat = incl_vat
        self.last_fetched: dt_util.dt.datetime | None = None
        self.publication_timestamp: dt_util.dt.datetime | None = None

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
                grid_product=self._grid_product,
                region=self._region,
                start=start,
                end=end,
                incl_vat=self._incl_vat,
            )
            self.last_fetched = dt_util.now()
            # Fall back to fetch time when the API omits its publication timestamp.
            self.publication_timestamp = (
                self._api.publication_timestamp or self.last_fetched
            )
            await self._store.async_save(
                {
                    "slots": slots_to_json(slots),
                    "fetched_at": self.last_fetched.isoformat(),
                    "publication_timestamp": self.publication_timestamp.isoformat(),
                }
            )
            return slots
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch EKZ tariffs: {err}") from err


class EkzTariffsOAuthCoordinator(DataUpdateCoordinator[list[TariffSlot]]):
    """Coordinator for OAuth API (customer-specific tariffs)."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: EkzTariffsOAuthApi,
        store: Store,
        ems_instance_id: str,
        incl_vat: bool = False,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="EKZ Customer Tariffs",
            update_interval=None,
            config_entry=config_entry,
        )

        self._api = api
        self._store = store
        self._ems_instance_id = ems_instance_id
        self._incl_vat = incl_vat
        self.last_fetched: dt_util.dt.datetime | None = None
        self.publication_timestamp: dt_util.dt.datetime | None = None

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
                incl_vat=self._incl_vat,
            )
            self.last_fetched = dt_util.now()
            # Keep attribute behavior consistent with public API responses.
            self.publication_timestamp = (
                self._api.publication_timestamp or self.last_fetched
            )
            await self._store.async_save(
                {
                    "slots": slots_to_json(slots),
                    "fetched_at": self.last_fetched.isoformat(),
                    "publication_timestamp": self.publication_timestamp.isoformat(),
                }
            )
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
