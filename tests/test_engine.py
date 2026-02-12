import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.configuration import OUTPUT_MARKET_HUBS
from src.engine import CalculatorEngine


def test_refresh_data_and_export_csv(tmp_path: Path) -> None:
    config_path = Path("app_config.json")
    engine = CalculatorEngine(config_path)

    results = engine.refresh_data()
    assert len(results) == 2
    assert all(item.total_cost > 0 for item in results)

    out_csv = tmp_path / "output.csv"
    engine.export_csv(out_csv)
    text = out_csv.read_text(encoding="utf-8")
    assert "blueprint,material_cost,tax_cost,total_cost,last_refresh_utc" in text
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
