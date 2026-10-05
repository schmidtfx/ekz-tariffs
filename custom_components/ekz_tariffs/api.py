from __future__ import annotations

import asyncio
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
    ELECTRICITY_PRODUCT_BY_GRID_PRODUCT,
    VAT_RATE,
)

_LOGGER = logging.getLogger(__name__)


def _extract_chf_kwh(components: list[dict[str, Any]]) -> float | None:
    for comp in components:
        if comp.get("unit") == "CHF_kWh":
            value = comp.get("value")
            return float(value) if value is not None else None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


@dataclass(frozen=True)
class TariffSlot:
    start: datetime
    end: datetime
    price_chf_per_kwh: float
    integrated_chf_per_kwh: float | None = None
    electricity_chf_per_kwh: float | None = None
    grid_chf_per_kwh: float | None = None
    regional_fees_chf_per_kwh: float | None = None
    feed_in_chf_per_kwh: float | None = None


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
        self.publication_timestamp: datetime | None = None

    async def fetch_tariffs(
        self,
        grid_product: str,
        region: str | None,
        start: datetime,
        end: datetime,
        incl_vat: bool = False,
    ) -> list[TariffSlot]:
        """Fetch each selected public tariff component for a time range."""
        try:
            electricity_product = ELECTRICITY_PRODUCT_BY_GRID_PRODUCT[grid_product]
        except KeyError as err:
            raise ValueError(f"Unknown EKZ grid product: {grid_product}") from err

        start = dt_util.as_local(start)
        end = dt_util.as_local(end)

        requests = [
            self._fetch_component(
                start,
                end,
                tariff_name=f"grid_{grid_product}_inclFees",
            ),
            self._fetch_component(
                start,
                end,
                tariff_name=f"electricity_{electricity_product}",
            ),
            self._fetch_component(start, end, tariff_type="feed_in"),
        ]
        if region:
            requests.append(
                self._fetch_component(
                    start,
                    end,
                    tariff_name=f"regional_fees_{region}",
                )
            )
        responses = await asyncio.gather(*requests)

        grid_prices = _parse_component_values(responses[0][0], "grid")
        electricity_prices = _parse_component_values(responses[1][0], "electricity")
        feed_in_prices = _parse_component_values(responses[2][0], "feed_in")
        regional_prices = (
            _parse_component_values(responses[3][0], "regional_fees") if region else {}
        )
        self.publication_timestamp = _latest_publication_timestamp(
            timestamp for _, timestamp in responses
        )

        return _make_slots(
            grid_prices,
            electricity_prices,
            regional_prices,
            feed_in_prices,
            incl_vat,
            region_configured=bool(region),
        )

    async def _fetch_component(
        self,
        start: datetime,
        end: datetime,
        *,
        tariff_name: str | None = None,
        tariff_type: str | None = None,
    ) -> tuple[dict[str, Any], datetime | None]:
        params = {
            "start_timestamp": start.isoformat(timespec="seconds"),
            "end_timestamp": end.isoformat(timespec="seconds"),
        }
        if tariff_name:
            params["tariff_name"] = tariff_name
        if tariff_type:
            params["tariff_type"] = tariff_type

        async with self._session.get(
            f"{API_BASE}{API_TARIFFS_PATH}", params=params, timeout=30
        ) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        published = _parse_datetime(data.get("publication_timestamp"))
        return data, dt_util.as_local(published) if published else None


def _parse_component_values(
    data: dict[str, Any], component_name: str
) -> dict[tuple[datetime, datetime], float]:
    values: dict[tuple[datetime, datetime], float] = {}
    for item in data.get("prices", []):
        start_ts = _parse_datetime(item.get("start_timestamp"))
        end_ts = _parse_datetime(item.get("end_timestamp"))
        if start_ts is None or end_ts is None:
            continue
        value = _extract_chf_kwh(item.get(component_name, []))
        if value is not None:
            values[(dt_util.as_utc(start_ts), dt_util.as_utc(end_ts))] = value
    return values


def _latest_publication_timestamp(
    timestamps: Any,
) -> datetime | None:
    available = [timestamp for timestamp in timestamps if timestamp is not None]
    return max(available, key=dt_util.as_utc) if available else None


def _make_slots(
    grid_prices: dict[tuple[datetime, datetime], float],
    electricity_prices: dict[tuple[datetime, datetime], float],
    regional_prices: dict[tuple[datetime, datetime], float],
    feed_in_prices: dict[tuple[datetime, datetime], float],
    incl_vat: bool,
    *,
    region_configured: bool,
) -> list[TariffSlot]:
    keys = sorted(set(grid_prices) | set(electricity_prices))
    slots: list[TariffSlot] = []
    vat_multiplier = 1 + VAT_RATE if incl_vat else 1.0
    for start, end in keys:
        grid = grid_prices.get((start, end))
        electricity = electricity_prices.get((start, end))
        if grid is None or electricity is None:
            continue
        regional = regional_prices.get((start, end))
        if region_configured and regional is None:
            continue
        regional = regional or 0.0
        feed_in = feed_in_prices.get((start, end))
        integrated = grid + electricity
        slots.append(
            TariffSlot(
                start=dt_util.as_local(start),
                end=dt_util.as_local(end),
                price_chf_per_kwh=round((integrated + regional) * vat_multiplier, 4),
                integrated_chf_per_kwh=round(integrated * vat_multiplier, 4),
                electricity_chf_per_kwh=round(electricity * vat_multiplier, 4),
                grid_chf_per_kwh=round(grid * vat_multiplier, 4),
                regional_fees_chf_per_kwh=round(regional * vat_multiplier, 4),
                feed_in_chf_per_kwh=(
                    round(feed_in, 4) if feed_in is not None else None
                ),
            )
        )
    return slots


class EkzTariffsOAuthApi:
    """API client for EKZ authenticated endpoints using OAuth2."""

    def __init__(self, oauth_session: OAuth2Session, session: ClientSession):
        self._oauth_session = oauth_session
        self._session = session
        self.publication_timestamp: datetime | None = None

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

        self.publication_timestamp = _parse_datetime(data.get("publication_timestamp"))
        if self.publication_timestamp is not None:
            self.publication_timestamp = dt_util.as_local(self.publication_timestamp)

        slots: list[TariffSlot] = []
        for item in data.get("prices", []):
            start_ts = _parse_datetime(item.get("start_timestamp"))
            end_ts = _parse_datetime(item.get("end_timestamp"))
            if start_ts is None or end_ts is None:
                continue
            grid = _extract_chf_kwh(item.get("grid", []))
            electricity = _extract_chf_kwh(item.get("electricity", []))
            regional = _extract_chf_kwh(item.get("regional_fees", [])) or 0.0
            integrated = _extract_chf_kwh(item.get("integrated", []))
            if grid is not None and electricity is not None:
                integrated_price = grid + electricity
            elif integrated is not None:
                integrated_price = integrated
            else:
                continue
            price = integrated_price + regional
            feed_in = _extract_chf_kwh(item.get("feed_in", []))

            vat_multiplier = 1 + VAT_RATE if incl_vat else 1.0

            slots.append(
                TariffSlot(
                    start=dt_util.as_local(start_ts),
                    end=dt_util.as_local(end_ts),
                    price_chf_per_kwh=round(price * vat_multiplier, 4),
                    integrated_chf_per_kwh=round(integrated_price * vat_multiplier, 4),
                    electricity_chf_per_kwh=(
                        round(electricity * vat_multiplier, 4)
                        if electricity is not None
                        else None
                    ),
                    grid_chf_per_kwh=(
                        round(grid * vat_multiplier, 4) if grid is not None else None
                    ),
                    regional_fees_chf_per_kwh=round(regional * vat_multiplier, 4),
                    feed_in_chf_per_kwh=(
                        round(feed_in, 4) if feed_in is not None else None
                    ),
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
