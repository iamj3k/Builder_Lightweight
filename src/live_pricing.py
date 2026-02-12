from __future__ import annotations

from typing import Any

from .engine import LivePriceProvider


class ConfigJitaLivePriceProvider(LivePriceProvider):
    """Simple live Jita pricing provider driven by config payloads.

    In production this can be replaced with an ESI-backed fetcher while preserving
    the same interface.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._rows = config.get("live_jita_prices", {})

    def get_sell_price(self, item_name: str) -> float | None:
        row = self._rows.get(item_name)
        if not row:
            return None
        value = row.get("sell_price")
        if value is None:
            return None
        return float(value)
