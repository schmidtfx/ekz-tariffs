from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientSession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE,
    API_CUSTOMER_TARIFFS_PATH,
    API_EMS_LINK_STATUS_PATH,
    API_TARIFFS_PATH,
    INTEGRATED_PREFIX,
    VAT_RATE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TariffSlot:
    start: datetime
    end: datetime
    price_chf_per_kwh: float


@dataclass(frozen=True)
class CustomerTariff:
    """Customer-specific tariff information."""

    tariff_name: str
    metering_point_id: str | None = None


@dataclass(frozen=True)
class EMSLinkStatus:
    """EMS link status information."""

    is_linked: bool
    ems_instance_id: str | None = None


class EkzTariffsApi:
    """API client for EKZ public tariffs."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def fetch_tariffs(
        self,
        tariff_name: str,
        start: datetime,
        end: datetime,
        incl_vat: bool = False,
        incl_regional_fees: bool = False,
    ) -> list[TariffSlot]:
        """Fetch tariff slots from EKZ public API for time range."""
        start = dt_util.as_local(start)
        end = dt_util.as_local(end)

        params = {
            "tariff_name": f"{INTEGRATED_PREFIX}{tariff_name}",
            "start_timestamp": start.isoformat(timespec="seconds"),
            "end_timestamp": end.isoformat(timespec="seconds"),
        }

        url = f"{API_BASE}{API_TARIFFS_PATH}"

        async with self._session.get(url, params=params, timeout=30) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        # Fetch regional fees if requested
        regional_fee = 0.0
        if incl_regional_fees:
            regional_fee = await self._fetch_regional_fee()

        return self._parse_tariff_slots(
            data, incl_vat=incl_vat, regional_fee=regional_fee
        )

    async def _fetch_regional_fee(self) -> float:
        """Fetch regional fees from EKZ API.
        
        Returns the cantonal tax for Canton ZH (0.0016 CHF/kWh).
        For customer-specific fees, OAuth API should be used.
        """
        try:
            # Try to fetch regional fees from API
            # Note: The API structure shows regional_fees as a separate tariff type
            # For public API users, we'll use the Canton ZH default
            # This could be extended to be configurable per municipality
            
            # Default to Canton ZH fee (Förderung Energieeffizienz)
            return 0.0016
        except Exception as err:
            _LOGGER.warning(
                "Could not fetch regional fees from API, using default: %s", err
            )
            return 0.0016

    def _parse_tariff_slots(
        self, data: dict[str, Any], incl_vat: bool = False, regional_fee: float = 0.0
    ) -> list[TariffSlot]:
        """Parse tariff slots from API response."""
        slots: list[TariffSlot] = []
        for item in data.get("prices", []):
            start_ts = dt_util.parse_datetime(item["start_timestamp"])
            end_ts = dt_util.parse_datetime(item["end_timestamp"])
            if start_ts is None or end_ts is None:
                continue
            price_val = None
            for comp in item.get("integrated", []):
                if comp.get("unit") == "CHF_kWh":
                    price_val = comp.get("value")
                    if incl_vat:
                        price_val = price_val * (1 + VAT_RATE)
                    # Add regional fees if applicable
                    if regional_fee > 0:
                        price_val = price_val + regional_fee
                    break

            if price_val is None:
                continue

            slots.append(
                TariffSlot(
                    start=dt_util.as_local(start_ts),
                    end=dt_util.as_local(end_ts),
                    price_chf_per_kwh=float(price_val),
                )
            )

        slots.sort(key=lambda s: s.start)
        return slots


class EkzTariffsOAuthApi:
    """API client for EKZ authenticated endpoints using OAuth2."""

    def __init__(self, oauth_session: OAuth2Session, session: ClientSession):
        self._oauth_session = oauth_session
        self._session = session

    async def _get_headers(self) -> dict[str, str]:
        """Get authorization headers with valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return {
            "Authorization": f"Bearer {self._oauth_session.token['access_token']}",
        }

    async def fetch_customer_tariffs(
        self,
        ems_instance_id: str,
        start: datetime,
        end: datetime,
        incl_vat: bool = False,
        incl_regional_fees: bool = False,
    ) -> list[TariffSlot]:
        """Fetch customer-specific tariffs from authenticated API."""
        start = dt_util.as_local(start)
        end = dt_util.as_local(end)

        params = {
            "ems_instance_id": ems_instance_id,
            "start_timestamp": start.isoformat(timespec="seconds"),
            "end_timestamp": end.isoformat(timespec="seconds"),
        }

        url = f"{API_BASE}{API_CUSTOMER_TARIFFS_PATH}"
        headers = await self._get_headers()

        async with self._session.get(
            url, params=params, headers=headers, timeout=30
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                _LOGGER.error(
                    "Customer tariffs request failed with %s: %s",
                    resp.status,
                    error_text,
                )
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        # Fetch regional fees if requested
        regional_fee = 0.0
        if incl_regional_fees:
            # For OAuth users, the integrated price might already include regional fees
            # Check if the API response includes regional fee information
            # For now, use the same default as public API
            regional_fee = 0.0016

        # Parse the response similar to public API
        slots: list[TariffSlot] = []
        for item in data.get("prices", []):
            start_ts = dt_util.parse_datetime(item["start_timestamp"])
            end_ts = dt_util.parse_datetime(item["end_timestamp"])
            if start_ts is None or end_ts is None:
                continue
            price_val = None
            for comp in item.get("integrated", []):
                if comp.get("unit") == "CHF_kWh":
                    price_val = comp.get("value")
                    if incl_vat:
                        price_val = price_val * (1 + VAT_RATE)
                    # Add regional fees if applicable
                    if regional_fee > 0:
                        price_val = price_val + regional_fee
                    break

            if price_val is None:
                continue

            slots.append(
                TariffSlot(
                    start=dt_util.as_local(start_ts),
                    end=dt_util.as_local(end_ts),
                    price_chf_per_kwh=float(price_val),
                )
            )

        slots.sort(key=lambda s: s.start)
        return slots

    async def check_ems_link_status(
        self, ems_instance_id: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Check EMS link status and get linking URL if needed."""
        url = f"{API_BASE}{API_EMS_LINK_STATUS_PATH}"
        headers = await self._get_headers()

        params = {
            "ems_instance_id": ems_instance_id,
            "redirect_uri": redirect_uri,
        }

        _LOGGER.debug("Checking EMS link status for instance: %s", ems_instance_id)

        async with self._session.get(
            url, params=params, headers=headers, timeout=30
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                _LOGGER.error(
                    "EMS link status check failed with %s: %s",
                    resp.status,
                    error_text,
                )
                _LOGGER.error("Request URL: %s", url)
                _LOGGER.error("Request params: %s", params)
                # Don't raise, return error info instead
                return {
                    "error": True,
                    "status": resp.status,
                    "message": error_text,
                }
            data: dict[str, Any] = await resp.json()

        _LOGGER.debug("EMS link status response: %s", data)
        return data

    async def fetch_ems_link_status(self) -> EMSLinkStatus:
        """Fetch EMS link status from authenticated API (simple check)."""
        url = f"{API_BASE}{API_EMS_LINK_STATUS_PATH}"
        headers = await self._get_headers()

        async with self._session.get(url, headers=headers, timeout=30) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        return EMSLinkStatus(
            is_linked=data.get("is_linked", False),
            ems_instance_id=data.get("ems_instance_id"),
        )
