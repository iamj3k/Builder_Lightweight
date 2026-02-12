from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .providers import CharacterStateRecord, MarketSnapshotRecord


class LocalSQLiteCache:
    """Local cache for market/character snapshots and computed build costs."""

    def __init__(
        self,
        db_path: Path,
        *,
        market_ttl_seconds: int = 600,
        character_ttl_seconds: int = 180,
    ) -> None:
        self.db_path = db_path
        self.market_ttl_seconds = market_ttl_seconds
        self.character_ttl_seconds = character_ttl_seconds
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    hub_name TEXT NOT NULL,
                    snapshot_ts INTEGER NOT NULL,
                    type_id INTEGER,
                    item_name TEXT NOT NULL,
                    sell_price REAL NOT NULL,
                    buy_price REAL NOT NULL,
                    daily_volume REAL NOT NULL,
                    PRIMARY KEY (hub_name, snapshot_ts, type_id, item_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS character_assets_snapshots (
                    snapshot_ts INTEGER NOT NULL,
                    type_id INTEGER,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    PRIMARY KEY (snapshot_ts, type_id, item_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS character_open_orders_snapshots (
                    snapshot_ts INTEGER NOT NULL,
                    type_id INTEGER,
                    item_name TEXT NOT NULL,
                    volume_remain INTEGER NOT NULL,
                    PRIMARY KEY (snapshot_ts, type_id, item_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS build_cost_cache (
                    config_hash TEXT PRIMARY KEY,
                    computed_ts INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def save_market_snapshot(self, hub_name: str, records: list[MarketSnapshotRecord], *, now_ts: int | None = None) -> int:
        ts = now_ts or int(time.time())
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO market_snapshots
                (hub_name, snapshot_ts, type_id, item_name, sell_price, buy_price, daily_volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        hub_name,
                        ts,
                        record.key.type_id,
                        record.key.item_name,
                        record.sell_price,
                        record.buy_price,
                        record.daily_volume,
                    )
                    for record in records
                ],
            )
        return ts

    def get_market_snapshot(self, hub_name: str, *, now_ts: int | None = None) -> list[dict[str, Any]] | None:
        ts = now_ts or int(time.time())
        oldest_allowed = ts - self.market_ttl_seconds
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(snapshot_ts) AS snapshot_ts
                FROM market_snapshots
                WHERE hub_name = ?
                """,
                (hub_name,),
            ).fetchone()
            if not row or row["snapshot_ts"] is None or int(row["snapshot_ts"]) < oldest_allowed:
                return None

            latest_ts = int(row["snapshot_ts"])
            rows = conn.execute(
                """
                SELECT type_id, item_name, sell_price, buy_price, daily_volume
                FROM market_snapshots
                WHERE hub_name = ? AND snapshot_ts = ?
                """,
                (hub_name, latest_ts),
            ).fetchall()
            return [dict(r) for r in rows]

    def save_character_snapshot(self, records: list[CharacterStateRecord], *, now_ts: int | None = None) -> int:
        ts = now_ts or int(time.time())
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO character_assets_snapshots
                (snapshot_ts, type_id, item_name, quantity)
                VALUES (?, ?, ?, ?)
                """,
                [(ts, r.key.type_id, r.key.item_name, r.asset_quantity) for r in records],
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO character_open_orders_snapshots
                (snapshot_ts, type_id, item_name, volume_remain)
                VALUES (?, ?, ?, ?)
                """,
                [(ts, r.key.type_id, r.key.item_name, r.open_order_quantity) for r in records],
            )
        return ts

    def get_character_snapshot(self, *, now_ts: int | None = None) -> dict[str, list[dict[str, Any]]] | None:
        ts = now_ts or int(time.time())
        oldest_allowed = ts - self.character_ttl_seconds
        with self._connect() as conn:
            assets_ts = conn.execute("SELECT MAX(snapshot_ts) AS snapshot_ts FROM character_assets_snapshots").fetchone()
            orders_ts = conn.execute("SELECT MAX(snapshot_ts) AS snapshot_ts FROM character_open_orders_snapshots").fetchone()
            if not assets_ts or not orders_ts:
                return None
            latest_assets = assets_ts["snapshot_ts"]
            latest_orders = orders_ts["snapshot_ts"]
            if latest_assets is None or latest_orders is None:
                return None
            latest_ts = min(int(latest_assets), int(latest_orders))
            if latest_ts < oldest_allowed:
                return None

            assets = conn.execute(
                """
                SELECT type_id, item_name, quantity
                FROM character_assets_snapshots
                WHERE snapshot_ts = ?
                """,
                (latest_ts,),
            ).fetchall()
            orders = conn.execute(
                """
                SELECT type_id, item_name, volume_remain
                FROM character_open_orders_snapshots
                WHERE snapshot_ts = ?
                """,
                (latest_ts,),
            ).fetchall()
            return {
                "assets": [dict(r) for r in assets],
                "open_orders": [dict(r) for r in orders],
            }

    def get_build_cost(self, config_hash: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM build_cost_cache WHERE config_hash = ?",
                (config_hash,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload_json"])
            return payload

    def save_build_cost(self, config_hash: str, cost: dict[str, Any], *, now_ts: int | None = None) -> None:
        ts = now_ts or int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO build_cost_cache (config_hash, computed_ts, payload_json)
                VALUES (?, ?, ?)
                """,
                (config_hash, ts, json.dumps(cost, sort_keys=True)),
            )
