from __future__ import annotations

import datetime as dt

from custom_components.ekz_tariffs.storage import slots_from_json, slots_to_json

from tests.conftest import make_slots


def test_storage_round_trips_integrated_and_total_prices(fixed_now):
    slots = make_slots(
        fixed_now,
        [0.36],
        feed_in=[0.05],
    )
    serialized = slots_to_json(slots)
    restored = slots_from_json(serialized)

    assert restored[0].integrated_chf_per_kwh == 0.36
    assert restored[0].price_chf_per_kwh == 0.36
    assert restored[0].feed_in_chf_per_kwh == 0.05


def test_old_cached_components_can_reconstruct_integrated_price(fixed_now):
    end = fixed_now + dt.timedelta(minutes=15)
    old_cache = [
        {
            "start": fixed_now.isoformat(),
            "end": end.isoformat(),
            "price": 0.36,
            "electricity": 0.10,
            "grid": 0.20,
            "regional_fees": 0.06,
        }
    ]

    restored = slots_from_json(old_cache)

    assert restored[0].integrated_chf_per_kwh == 0.30
    assert restored[0].price_chf_per_kwh == 0.36
