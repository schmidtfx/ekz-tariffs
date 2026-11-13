from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import TariffSlot

STORAGE_VERSION = 1


def slots_to_json(slots: list[TariffSlot]) -> list[dict[str, Any]]:
    return [
        {
            "start": s.start.isoformat(),
            "end": s.end.isoformat(),
            # Keep "price" as the total for compatibility with existing cache data.
            "price": s.price_chf_per_kwh,
            "integrated": s.integrated_chf_per_kwh,
            "electricity": s.electricity_chf_per_kwh,
            "grid": s.grid_chf_per_kwh,
            "regional_fees": s.regional_fees_chf_per_kwh,
            "feed_in": s.feed_in_chf_per_kwh,
        }
        for s in slots
    ]


def slots_from_json(raw: list[dict[str, Any]]) -> list[TariffSlot]:
    out: list[TariffSlot] = []
    for item in raw:
        start = dt_util.parse_datetime(item["start"])
        end = dt_util.parse_datetime(item["end"])
        if start is None or end is None:
            continue
        feed_in = item.get("feed_in")
        electricity = item.get("electricity")
        grid = item.get("grid")
        regional_fees = item.get("regional_fees")
        integrated = item.get("integrated")
        if integrated is None and electricity is not None and grid is not None:
            # Older/newer cache records may lack the explicit integrated subtotal.
            integrated = round(float(electricity) + float(grid), 4)
        out.append(
            TariffSlot(
                start=dt_util.as_local(start),
                end=dt_util.as_local(end),
                price_chf_per_kwh=float(item["price"]),
                integrated_chf_per_kwh=(
                    float(integrated) if integrated is not None else None
                ),
                electricity_chf_per_kwh=(
                    float(electricity) if electricity is not None else None
                ),
                grid_chf_per_kwh=float(grid) if grid is not None else None,
                regional_fees_chf_per_kwh=(
                    float(regional_fees) if regional_fees is not None else None
                ),
                feed_in_chf_per_kwh=float(feed_in) if feed_in is not None else None,
            )
        )
    out.sort(key=lambda s: s.start)
    return out


def make_store(hass, entry_id: str) -> Store:
    # Unique key per config entry
    return Store(hass, STORAGE_VERSION, f"ekz_tariffs.{entry_id}")
