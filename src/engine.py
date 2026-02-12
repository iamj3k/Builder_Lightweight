from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import LocalSQLiteCache
from .configuration import ensure_blueprint_whitelisted, get_me_te_for_blueprint


@dataclass
class BlueprintCost:
    name: str
    material_cost: float
    tax_cost: float
    total_cost: float


class CalculatorEngine:
    """Small calculator engine used by the desktop launcher."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config: dict[str, Any] = {}
        self.last_refresh: datetime | None = None
        self.results: list[BlueprintCost] = []
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

            bp_me, _ = get_me_te_for_blueprint(bp["name"], default_me=default_me, default_te=default_te)
            me_bonus = (100 - bp_me) / 100
            material_cost = 0.0
            for material, amount in bp["materials"].items():
                unit_price = float(prices.get(material, 0))
                material_cost += amount * me_bonus * unit_price
            tax_cost = material_cost * tax_rate
            total_cost = material_cost + tax_cost
            row = BlueprintCost(
                name=bp["name"],
                material_cost=round(material_cost, 2),
                tax_cost=round(tax_cost, 2),
                total_cost=round(total_cost, 2),
            )
            refreshed.append(row)
            self.cache.save_build_cost(cache_key, cost=row.__dict__)

        self.results = refreshed
        self.last_refresh = datetime.now(timezone.utc)
        return refreshed

    @staticmethod
    def _blueprint_config_hash(bp: dict[str, Any], defaults: dict[str, Any], prices: dict[str, Any]) -> str:
        relevant_prices = {name: prices.get(name, 0) for name in sorted(bp["materials"])}
        payload = {
            "blueprint": bp,
            "defaults": {
                "tax_rate": defaults["tax_rate"],
                "me": defaults["me"],
                "te": defaults["te"],
            },
            "prices": relevant_prices,
        }
        digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def export_csv(self, target_path: Path) -> Path:
        if not self.results:
            self.refresh_data()

        with target_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["blueprint", "material_cost", "tax_cost", "total_cost", "last_refresh_utc"])
            timestamp = self.last_refresh.isoformat() if self.last_refresh else ""
            for row in self.results:
                writer.writerow([row.name, row.material_cost, row.tax_cost, row.total_cost, timestamp])
        return target_path
