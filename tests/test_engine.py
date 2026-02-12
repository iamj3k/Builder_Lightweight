import csv
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.configuration import MARKET_HUB_LOCATION_IDS, OUTPUT_MARKET_HUBS
from src.build_plan import STATIC_BUILD_QUANTITIES
from src.engine import CSV_EXPORT_HEADERS, CalculatorEngine, LivePriceProvider


class StubLivePriceProvider(LivePriceProvider):
    def __init__(self, sell_prices: dict[str, float]) -> None:
        self._prices = sell_prices

    def get_sell_price(self, item_name: str) -> float | None:
        return self._prices.get(item_name)


def test_refresh_data_and_export_csv(tmp_path: Path) -> None:
    config_path = Path("app_config.json")
    engine = CalculatorEngine(config_path)

    results = engine.refresh_data()
    assert len(results) == 2
    assert all(item.total_cost > 0 for item in results)

    out_csv = tmp_path / "output.csv"
    engine.export_csv(out_csv)
    text = out_csv.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(CSV_EXPORT_HEADERS)
    assert "Rifter" in text


def test_rejects_non_whitelisted_blueprint(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "defaults": {"me": 10, "te": 20, "tax_rate": 0.08},
          "blueprints": [
            {"name": "Forbidden BP", "materials": {"Tritanium": 1}}
          ],
          "price_overrides": {"Tritanium": 1}
        }
        """,
        encoding="utf-8",
    )

    engine = CalculatorEngine(config_path)
    with pytest.raises(ValueError, match="not whitelisted"):
        engine.refresh_data()


def test_output_market_hubs_list() -> None:
    assert OUTPUT_MARKET_HUBS == ["Jita", "Amarr", "Dodixie", "O-PNSN", "C-N4OD"]


def test_csv_export_header_schema_is_fixed() -> None:
    assert CSV_EXPORT_HEADERS == [
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


def test_market_hub_location_ids_are_explicit_and_stable() -> None:
    assert MARKET_HUB_LOCATION_IDS == {
        "Jita": [60003760, 1022734985679],
        "Amarr": [60008494],
        "Dodixie": [60011866],
        "O-PNSN": [1036927076065],
        "C-N4OD": [1037131880317],
    }


def test_export_uses_character_state_and_multi_hub_market_data(tmp_path: Path) -> None:
    engine = CalculatorEngine(Path("app_config.json"))
    engine.refresh_data()
    engine.attach_character_state(
        oauth_token="token",
        asset_rows=[
            {"item_name": "Rifter", "type_id": 587, "location_id": 60003760, "quantity": 4},
            {"item_name": "Rifter", "type_id": 587, "location_id": 1022734985679, "quantity": 2},
            {"item_name": "Merlin", "type_id": 603, "location_id": 60008494, "quantity": 3},
        ],
        order_rows=[
            {"item_name": "Rifter", "type_id": 587, "location_id": 60003760, "volume_remain": 1},
            {"item_name": "Rifter", "type_id": 587, "location_id": 1022734985679, "volume_remain": 2},
            {"item_name": "Merlin", "type_id": 603, "location_id": 60008494, "volume_remain": 1},
        ],
    )

    out_csv = tmp_path / "full_output.csv"
    engine.export_csv(out_csv)

    with out_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    rifter = next(row for row in rows if row["item_name"] == "Rifter")
    assert rifter["quantity"] == "0"
    assert rifter["jita_stock"] == "6"
    assert rifter["jita_on_market"] == "3"
    assert rifter["jita_sell_price"] == "550000.0"
    assert rifter["amarr_sell_price"] == "565000.0"


def test_export_prefers_live_jita_price_provider(tmp_path: Path) -> None:
    engine = CalculatorEngine(Path("app_config.json"))
    engine.refresh_data()

    out_csv = tmp_path / "jita_live.csv"
    engine.export_csv(out_csv, live_price_provider=StubLivePriceProvider({"Rifter": 777777.0}))

    with out_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    rifter = next(row for row in rows if row["item_name"] == "Rifter")
    assert rifter["jita_sell_price"] == "777777.0"


def test_static_build_quantities_include_user_blueprints_and_merge_duplicates() -> None:
    assert STATIC_BUILD_QUANTITIES["10MN Afterburner II"] == 1296
    assert STATIC_BUILD_QUANTITIES["Bustard"] == 50
    assert STATIC_BUILD_QUANTITIES["Signal Amplifier II"] == 12965
    assert STATIC_BUILD_QUANTITIES["Complex Asteroid Mining Crystal Type A II"] == 37926
