from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
            bp_me, _ = get_me_te_for_blueprint(bp["name"], default_me=default_me, default_te=default_te)
            me_bonus = (100 - bp_me) / 100
            material_cost = 0.0
            for material, amount in bp["materials"].items():
                unit_price = float(prices.get(material, 0))
                material_cost += amount * me_bonus * unit_price
            tax_cost = material_cost * tax_rate
            total_cost = material_cost + tax_cost
            refreshed.append(
                BlueprintCost(
                    name=bp["name"],
                    material_cost=round(material_cost, 2),
                    tax_cost=round(tax_cost, 2),
                    total_cost=round(total_cost, 2),
                )
            )

        self.results = refreshed
        self.last_refresh = datetime.now(timezone.utc)
        return refreshed

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
