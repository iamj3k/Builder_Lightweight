from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

from .cache import LocalSQLiteCache
from .build_plan import STATIC_BUILD_QUANTITIES
from .configuration import MARKET_HUB_LOCATION_IDS, OUTPUT_MARKET_HUBS, ensure_blueprint_whitelisted, get_me_te_for_blueprint
from .providers import EsiCharacterStateAdapter


CSV_EXPORT_HEADERS = [
    "item_name",
    "build_cost_per_unit",
    "volume",
    "top_market_group",
    "quantity",
    "jita_sell_price",
    "jita_on_market",
    "jita_stock",
    "jita_order_price",
    "jita_avg_daily_volume",
    "amarr_sell_price",
    "amarr_on_market",
    "amarr_stock",
    "amarr_order_price",
    "amarr_avg_daily_volume",
    "dodixie_sell_price",
    "dodixie_on_market",
    "dodixie_stock",
    "dodixie_order_price",
    "dodixie_avg_daily_volume",
    "o-pnsn_sell_price",
    "o-pnsn_on_market",
    "o-pnsn_stock",
    "o-pnsn_order_price",
    "o-pnsn_avg_daily_volume",
    "c-n4od_sell_price",
    "c-n4od_on_market",
    "c-n4od_stock",
    "c-n4od_order_price",
    "c-n4od_avg_daily_volume",
]


@dataclass
class BlueprintCost:
    name: str
    material_cost: float
    tax_cost: float
    total_cost: float


@dataclass
class MarketHubMetrics:
    sell_price: float = 0.0
    on_market: int = 0
    stock: int = 0
    order_price: float = 0.0
    avg_daily_volume: float = 0.0


class LivePriceProvider:
    """Protocol-like base class for optional live pricing integrations."""

    def get_sell_price(self, item_name: str) -> float | None:
        return None


class CalculatorEngine:
    """Small calculator engine used by the desktop launcher."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config: dict[str, Any] = {}
        self.last_refresh: datetime | None = None
        self.results: list[BlueprintCost] = []
        self._character_adapter: EsiCharacterStateAdapter | None = None
        self.cache = LocalSQLiteCache(config_path.with_suffix(".cache.sqlite3"))
        self.load_config()

    def load_config(self) -> None:
        with self.config_path.open("r", encoding="utf-8") as f:
            self.config = json.load(f)

    def refresh_data(self) -> list[BlueprintCost]:
        """Recalculate costs from the fixed bundled config."""
        defaults = self.config["defaults"]
        tax_rate = float(defaults["tax_rate"])
        default_me = int(defaults["me"])
        default_te = int(defaults["te"])
        prices = self.config.get("price_overrides", {})

        refreshed: list[BlueprintCost] = []
        for bp in self.config["blueprints"]:
            ensure_blueprint_whitelisted(bp)
            cache_key = self._blueprint_config_hash(bp=bp, defaults=defaults, prices=prices)
            cached = self.cache.get_build_cost(cache_key)
            if cached is not None:
                refreshed.append(BlueprintCost(**cached))
                continue

            bp_name = str(bp["name"])
            build_quantity = int(STATIC_BUILD_QUANTITIES.get(bp_name, 1))
            bp_me, _ = get_me_te_for_blueprint(bp_name, default_me=default_me, default_te=default_te)
            me_bonus = (100 - bp_me) / 100
            total_material_cost = 0.0
            for material, amount in bp["materials"].items():
                unit_price = float(prices.get(material, 0))
                required_for_batch = ceil(float(amount) * build_quantity * me_bonus)
                total_material_cost += required_for_batch * unit_price

            material_cost_per_unit = total_material_cost / build_quantity
            tax_cost = material_cost_per_unit * tax_rate
            total_cost = material_cost_per_unit + tax_cost
            row = BlueprintCost(
                name=bp_name,
                material_cost=round(material_cost_per_unit, 2),
                tax_cost=round(tax_cost, 2),
                total_cost=round(total_cost, 2),
            )
            refreshed.append(row)
            self.cache.save_build_cost(cache_key, cost=row.__dict__)

        self.results = refreshed
        self.last_refresh = datetime.now(timezone.utc)
        return refreshed

    def attach_character_state(self, oauth_token: str, asset_rows: list[dict[str, Any]], order_rows: list[dict[str, Any]]) -> None:
        """Attach ESI-backed character state used for quantity and hub stock/on_market columns."""
        self._character_adapter = EsiCharacterStateAdapter(
            oauth_token=oauth_token,
            asset_rows=asset_rows,
            order_rows=order_rows,
        )

    @staticmethod
    def _blueprint_config_hash(bp: dict[str, Any], defaults: dict[str, Any], prices: dict[str, Any]) -> str:
        relevant_prices = {name: prices.get(name, 0) for name in sorted(bp["materials"])}
        build_quantity = int(STATIC_BUILD_QUANTITIES.get(str(bp.get("name", "")), 1))
        payload = {
            "blueprint": bp,
            "defaults": {
                "tax_rate": defaults["tax_rate"],
                "me": defaults["me"],
                "te": defaults["te"],
            },
            "prices": relevant_prices,
            "build_quantity": build_quantity,
        }
        digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def export_csv(self, target_path: Path, *, live_price_provider: LivePriceProvider | None = None) -> Path:
        if not self.results:
            self.refresh_data()

        market_overrides: dict[str, dict[str, Any]] = self.config.get("hub_market_overrides", {})
        hub_state_records = (
            self._character_adapter.get_hub_state_records(MARKET_HUB_LOCATION_IDS)
            if self._character_adapter
            else {}
        )
        with target_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_EXPORT_HEADERS)
            for row in self.results:
                quantity = int(STATIC_BUILD_QUANTITIES.get(row.name, 0))

                hub_metrics = self._resolve_hub_metrics(
                    item_name=row.name,
                    market_overrides=market_overrides,
                    hub_state_records=hub_state_records,
                    live_price_provider=live_price_provider,
                )

                writer.writerow(
                    [
                        row.name,
                        row.total_cost,
                        "",
                        "",
                        quantity,
                        hub_metrics["Jita"].sell_price,
                        hub_metrics["Jita"].on_market,
                        hub_metrics["Jita"].stock,
                        hub_metrics["Jita"].order_price,
                        hub_metrics["Jita"].avg_daily_volume,
                        hub_metrics["Amarr"].sell_price,
                        hub_metrics["Amarr"].on_market,
                        hub_metrics["Amarr"].stock,
                        hub_metrics["Amarr"].order_price,
                        hub_metrics["Amarr"].avg_daily_volume,
                        hub_metrics["Dodixie"].sell_price,
                        hub_metrics["Dodixie"].on_market,
                        hub_metrics["Dodixie"].stock,
                        hub_metrics["Dodixie"].order_price,
                        hub_metrics["Dodixie"].avg_daily_volume,
                        hub_metrics["O-PNSN"].sell_price,
                        hub_metrics["O-PNSN"].on_market,
                        hub_metrics["O-PNSN"].stock,
                        hub_metrics["O-PNSN"].order_price,
                        hub_metrics["O-PNSN"].avg_daily_volume,
                        hub_metrics["C-N4OD"].sell_price,
                        hub_metrics["C-N4OD"].on_market,
                        hub_metrics["C-N4OD"].stock,
                        hub_metrics["C-N4OD"].order_price,
                        hub_metrics["C-N4OD"].avg_daily_volume,
                    ]
                )
        return target_path

    def _resolve_hub_metrics(
        self,
        *,
        item_name: str,
        market_overrides: dict[str, dict[str, Any]],
        hub_state_records: dict[tuple[Any, str], Any],
        live_price_provider: LivePriceProvider | None,
    ) -> dict[str, MarketHubMetrics]:
        result = {hub_name: MarketHubMetrics() for hub_name in OUTPUT_MARKET_HUBS}
        lookup_name = item_name.strip().lower()

        for hub_name in OUTPUT_MARKET_HUBS:
            hub_rows = market_overrides.get(hub_name, {})
            for configured_name, row in hub_rows.items():
                if str(configured_name).strip().lower() != lookup_name:
                    continue
                result[hub_name].sell_price = float(row.get("sell_price", 0.0))
                result[hub_name].order_price = float(row.get("order_price", 0.0))
                result[hub_name].avg_daily_volume = float(row.get("avg_daily_volume", 0.0))

        if live_price_provider is not None:
            live_sell = live_price_provider.get_sell_price(item_name)
            if live_sell is not None:
                result["Jita"].sell_price = float(live_sell)

        for (key, hub_name), values in hub_state_records.items():
            if hub_name not in result:
                continue
            if key.item_name == lookup_name:
                result[hub_name].stock = int(values.stock)
                result[hub_name].on_market = int(values.on_market)

        return result
