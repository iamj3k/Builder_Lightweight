from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen


@dataclass(frozen=True)
class EveCookbookBlueprint:
    name: str
    materials: dict[str, float]
    material_prices: dict[str, float]


class EveCookbookClient:
    """Config-driven lightweight client for loading blueprint material data."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.enabled = bool(config.get("enabled", False))
        self.base_url = str(config.get("base_url", "")).rstrip("/")
        self.endpoint_template = str(
            config.get("blueprint_endpoint", "/api/blueprints/{blueprint_name}")
        )
        self.request_timeout_s = float(config.get("request_timeout_s", 15.0))

        # Response mapping allows compatibility with different EVE Cookbook payloads.
        self.materials_field = str(config.get("materials_field", "materials"))
        self.material_name_field = str(config.get("material_name_field", "name"))
        self.material_quantity_field = str(config.get("material_quantity_field", "quantity"))
        self.material_price_field = str(config.get("material_price_field", "adjusted_price"))

    def fetch_blueprint(self, blueprint_name: str) -> EveCookbookBlueprint:
        if not self.enabled:
            raise ValueError("EVE Cookbook integration is disabled in config.")
        if not self.base_url:
            raise ValueError("evecookbook.base_url must be configured when enabled.")

        endpoint = self.endpoint_template.format(blueprint_name=quote(blueprint_name, safe=""))
        url = f"{self.base_url}{endpoint}"
        with urlopen(url, timeout=self.request_timeout_s) as response:  # nosec B310 - config-driven URL required by feature
            payload = json.loads(response.read().decode("utf-8"))

        materials_raw = payload.get(self.materials_field, [])
        if not isinstance(materials_raw, list) or not materials_raw:
            raise ValueError(f"No materials found for '{blueprint_name}' from {url}.")

        materials: dict[str, float] = {}
        material_prices: dict[str, float] = {}
        for material_row in materials_raw:
            name = str(material_row.get(self.material_name_field, "")).strip()
            if not name:
                continue
            quantity = float(material_row.get(self.material_quantity_field, 0.0))
            if quantity <= 0:
                continue
            materials[name] = quantity

            price = material_row.get(self.material_price_field)
            if price is not None:
                material_prices[name] = float(price)

        if not materials:
            raise ValueError(f"EVE Cookbook returned no usable material rows for '{blueprint_name}'.")

        return EveCookbookBlueprint(
            name=blueprint_name,
            materials=materials,
            material_prices=material_prices,
        )
