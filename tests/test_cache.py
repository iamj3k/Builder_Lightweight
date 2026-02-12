import json
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.cache import LocalSQLiteCache
from src.engine import CalculatorEngine
from src.providers import CharacterStateRecord, ItemKey, MarketSnapshotRecord


def test_market_and_character_snapshots_obey_ttl(tmp_path: Path) -> None:
    cache = LocalSQLiteCache(tmp_path / "cache.sqlite3", market_ttl_seconds=600, character_ttl_seconds=120)

    market_records = [
        MarketSnapshotRecord(
            key=ItemKey(type_id=34, item_name="tritanium"),
            hub_name="Jita",
            sell_price=4.2,
            buy_price=4.1,
            daily_volume=1000,
        )
    ]
    character_records = [
        CharacterStateRecord(
            key=ItemKey(type_id=34, item_name="tritanium"),
            asset_quantity=10,
            open_order_quantity=2,
        )
    ]

    cache.save_market_snapshot("Jita", market_records, now_ts=1_000)
    cache.save_character_snapshot(character_records, now_ts=1_000)

    fresh_market = cache.get_market_snapshot("Jita", now_ts=1_200)
    fresh_character = cache.get_character_snapshot(now_ts=1_100)
    assert fresh_market is not None
    assert fresh_character is not None

    stale_market = cache.get_market_snapshot("Jita", now_ts=1_701)
    stale_character = cache.get_character_snapshot(now_ts=1_121)
    assert stale_market is None
    assert stale_character is None


def test_engine_recomputes_only_dirty_blueprint_configs(tmp_path: Path) -> None:
    config = {
        "defaults": {"me": 10, "te": 20, "tax_rate": 0.08},
        "blueprints": [
            {"name": "Rifter", "materials": {"Tritanium": 100}},
            {"name": "Merlin", "materials": {"Tritanium": 80}},
        ],
        "price_overrides": {"Tritanium": 5},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    engine = CalculatorEngine(config_path)
    first = engine.refresh_data()
    assert len(first) == 2

    conn = sqlite3.connect(config_path.with_suffix(".cache.sqlite3"))
    count_first = conn.execute("SELECT COUNT(*) FROM build_cost_cache").fetchone()[0]
    assert count_first == 2

    # Second run with same input should be fully cache-hit and keep same cache key count.
    second = engine.refresh_data()
    assert [r.total_cost for r in second] == [r.total_cost for r in first]
    count_second = conn.execute("SELECT COUNT(*) FROM build_cost_cache").fetchone()[0]
    assert count_second == 2

    # Change one blueprint material quantity so only one config hash becomes dirty.
    config["blueprints"][1]["materials"]["Tritanium"] = 90
    config_path.write_text(json.dumps(config), encoding="utf-8")
    engine.load_config()
    third = engine.refresh_data()

    count_third = conn.execute("SELECT COUNT(*) FROM build_cost_cache").fetchone()[0]
    assert count_third == 3
    assert third[0].total_cost == second[0].total_cost
    assert third[1].total_cost != second[1].total_cost
    conn.close()
