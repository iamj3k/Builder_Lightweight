import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.configuration import OUTPUT_MARKET_HUBS
from src.engine import CSV_EXPORT_HEADERS, CalculatorEngine


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
