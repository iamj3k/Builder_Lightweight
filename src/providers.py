from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ItemKey:
    """Canonical join key for any provider record."""

    type_id: int | None
    item_name: str

    @classmethod
    def from_raw(cls, *, type_id: Any, item_name: Any) -> "ItemKey":
        normalized_name = str(item_name or "").strip().lower()
        normalized_type_id = int(type_id) if type_id not in (None, "") else None

        if normalized_type_id is None and not normalized_name:
            raise ValueError("Each provider record must include type_id or item_name.")

        return cls(type_id=normalized_type_id, item_name=normalized_name)


@dataclass(frozen=True)
class CostRecord:
    key: ItemKey
    material_cost: float
    adjusted_price: float


@dataclass(frozen=True)
class CharacterStateRecord:
    key: ItemKey
    asset_quantity: int
    open_order_quantity: int


@dataclass(frozen=True)
class MarketSnapshotRecord:
    key: ItemKey
    hub_name: str
    sell_price: float
    buy_price: float
    daily_volume: float


@dataclass(frozen=True)
class AggregatedRecord:
    key: ItemKey
    cost: CostRecord | None
    character_state: CharacterStateRecord | None
    market_snapshot: MarketSnapshotRecord | None


class CostProvider(Protocol):
    """Normalized cost records (EVE Cookbook-backed)."""

    def get_cost_records(self) -> dict[ItemKey, CostRecord]:
        ...


class CharacterStateProvider(Protocol):
    """Normalized character state records (ESI assets/orders with OAuth)."""

    def get_character_state_records(self) -> dict[ItemKey, CharacterStateRecord]:
        ...


class MarketSnapshotProvider(Protocol):
    """Normalized market records (hub-specific sell/buy/volume metrics)."""

    def get_market_snapshot_records(self) -> dict[ItemKey, MarketSnapshotRecord]:
        ...


class EveCookbookCostAdapter(CostProvider):
    def __init__(self, cookbook_rows: Iterable[Mapping[str, Any]]) -> None:
        self.cookbook_rows = cookbook_rows

    def get_cost_records(self) -> dict[ItemKey, CostRecord]:
        normalized: dict[ItemKey, CostRecord] = {}
        for row in self.cookbook_rows:
            key = ItemKey.from_raw(type_id=row.get("type_id"), item_name=row.get("item_name"))
            normalized[key] = CostRecord(
                key=key,
                material_cost=float(row.get("material_cost", 0.0)),
                adjusted_price=float(row.get("adjusted_price", 0.0)),
            )
        return normalized


class EsiCharacterStateAdapter(CharacterStateProvider):
    """Adapter for ESI assets/orders that requires an OAuth token for initialization."""

    def __init__(
        self,
        oauth_token: str,
        asset_rows: Iterable[Mapping[str, Any]],
        order_rows: Iterable[Mapping[str, Any]],
    ) -> None:
        if not oauth_token.strip():
            raise ValueError("OAuth token is required for ESI-backed character state.")
        self.oauth_token = oauth_token
        self.asset_rows = asset_rows
        self.order_rows = order_rows

    def get_character_state_records(self) -> dict[ItemKey, CharacterStateRecord]:
        assets_by_key: dict[ItemKey, int] = {}
        for row in self.asset_rows:
            key = ItemKey.from_raw(type_id=row.get("type_id"), item_name=row.get("item_name"))
            assets_by_key[key] = assets_by_key.get(key, 0) + int(row.get("quantity", 0))

        orders_by_key: dict[ItemKey, int] = {}
        for row in self.order_rows:
            key = ItemKey.from_raw(type_id=row.get("type_id"), item_name=row.get("item_name"))
            orders_by_key[key] = orders_by_key.get(key, 0) + int(row.get("volume_remain", 0))

        joined_keys = set(assets_by_key) | set(orders_by_key)
        normalized: dict[ItemKey, CharacterStateRecord] = {}
        for key in joined_keys:
            normalized[key] = CharacterStateRecord(
                key=key,
                asset_quantity=assets_by_key.get(key, 0),
                open_order_quantity=orders_by_key.get(key, 0),
            )
        return normalized


class HubMarketSnapshotAdapter(MarketSnapshotProvider):
    def __init__(self, hub_name: str, snapshot_rows: Iterable[Mapping[str, Any]]) -> None:
        self.hub_name = hub_name
        self.snapshot_rows = snapshot_rows

    def get_market_snapshot_records(self) -> dict[ItemKey, MarketSnapshotRecord]:
        normalized: dict[ItemKey, MarketSnapshotRecord] = {}
        for row in self.snapshot_rows:
            key = ItemKey.from_raw(type_id=row.get("type_id"), item_name=row.get("item_name"))
            normalized[key] = MarketSnapshotRecord(
                key=key,
                hub_name=self.hub_name,
                sell_price=float(row.get("sell_price", 0.0)),
                buy_price=float(row.get("buy_price", 0.0)),
                daily_volume=float(row.get("daily_volume", 0.0)),
            )
        return normalized


class ProviderAggregator:
    """Joins normalized provider dictionaries using the shared ItemKey."""

    def __init__(
        self,
        cost_provider: CostProvider,
        character_state_provider: CharacterStateProvider,
        market_snapshot_provider: MarketSnapshotProvider,
    ) -> None:
        self.cost_provider = cost_provider
        self.character_state_provider = character_state_provider
        self.market_snapshot_provider = market_snapshot_provider

    def join_records(self) -> dict[ItemKey, AggregatedRecord]:
        costs = self.cost_provider.get_cost_records()
        states = self.character_state_provider.get_character_state_records()
        market = self.market_snapshot_provider.get_market_snapshot_records()

        joined_keys = set(costs) | set(states) | set(market)
        return {
            key: AggregatedRecord(
                key=key,
                cost=costs.get(key),
                character_state=states.get(key),
                market_snapshot=market.get(key),
            )
            for key in joined_keys
        }
