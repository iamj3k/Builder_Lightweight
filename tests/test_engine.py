from pathlib import Path

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
