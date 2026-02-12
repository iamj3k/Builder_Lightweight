import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.configuration import MARKET_HUB_LOCATION_IDS
from src.providers import (
    EveCookbookCostAdapter,
    EsiCharacterStateAdapter,
    HubMarketSnapshotAdapter,
    ItemKey,
    ProviderAggregator,
)


def test_adapters_return_normalized_records_keyed_by_type_id_or_item_name() -> None:
    costs = EveCookbookCostAdapter(
        [
            {"type_id": "34", "item_name": "Tritanium", "material_cost": 100, "adjusted_price": 4.2},
            {"item_name": "Pyerite", "material_cost": 50, "adjusted_price": 7.5},
        ]
    ).get_cost_records()

    state = EsiCharacterStateAdapter(
        oauth_token="token",
        asset_rows=[{"type_id": 34, "quantity": 10}],
        order_rows=[{"item_name": "Pyerite", "volume_remain": 4}],
    ).get_character_state_records()

    market = HubMarketSnapshotAdapter(
        hub_name="Jita",
        snapshot_rows=[
            {"type_id": 34, "sell_price": 4.3, "buy_price": 4.1, "daily_volume": 1000000},
            {"item_name": "Pyerite", "sell_price": 7.8, "buy_price": 7.0, "daily_volume": 500000},
        ],
    ).get_market_snapshot_records()

    assert ItemKey(type_id=34, item_name="tritanium") in costs
    assert ItemKey(type_id=None, item_name="pyerite") in costs
    assert ItemKey(type_id=34, item_name="") in state
    assert ItemKey(type_id=None, item_name="pyerite") in state
    assert ItemKey(type_id=34, item_name="") in market


def test_aggregator_joins_by_normalized_key() -> None:
    aggregator = ProviderAggregator(
        cost_provider=EveCookbookCostAdapter(
            [{"type_id": 34, "item_name": "Tritanium", "material_cost": 100, "adjusted_price": 4.2}]
        ),
        character_state_provider=EsiCharacterStateAdapter(
            oauth_token="token",
            asset_rows=[{"type_id": 34, "item_name": "Tritanium", "quantity": 20}],
            order_rows=[],
        ),
        market_snapshot_provider=HubMarketSnapshotAdapter(
            hub_name="Jita",
            snapshot_rows=[{"type_id": 34, "item_name": "tritanium", "sell_price": 4.4, "buy_price": 4.0, "daily_volume": 99}],
        ),
    )

    joined = aggregator.join_records()
    key = ItemKey(type_id=34, item_name="tritanium")

    assert key in joined
    assert joined[key].cost is not None
    assert joined[key].character_state is not None
    assert joined[key].market_snapshot is not None


def test_character_state_adapter_requires_oauth_token() -> None:
    with pytest.raises(ValueError, match="OAuth token"):
        EsiCharacterStateAdapter(oauth_token=" ", asset_rows=[], order_rows=[])


def test_hub_state_records_map_orders_and_assets_by_location_id() -> None:
    adapter = EsiCharacterStateAdapter(
        oauth_token="token",
        asset_rows=[
            {"type_id": 34, "item_name": "Tritanium", "location_id": 60003760, "quantity": 100},
            {"type_id": 34, "item_name": "Tritanium", "location_id": 1022734985679, "quantity": 25},
            {"type_id": 35, "item_name": "Pyerite", "location_id": 60008494, "quantity": 20},
            {"type_id": 34, "item_name": "Tritanium", "location_id": 42, "quantity": 999},
        ],
        order_rows=[
            {"type_id": 34, "item_name": "Tritanium", "location_id": 60003760, "volume_remain": 40},
            {"type_id": 34, "item_name": "Tritanium", "location_id": 1022734985679, "volume_remain": 10},
            {"type_id": 35, "item_name": "Pyerite", "location_id": 60008494, "volume_remain": 12},
            {"type_id": 34, "item_name": "Tritanium", "location_id": 42, "volume_remain": 777},
        ],
    )

    hub_state = adapter.get_hub_state_records(MARKET_HUB_LOCATION_IDS)

    jita_key = (ItemKey(type_id=34, item_name="tritanium"), "Jita")
    amarr_key = (ItemKey(type_id=35, item_name="pyerite"), "Amarr")

    assert hub_state[jita_key].stock == 125
    assert hub_state[jita_key].on_market == 50
    assert hub_state[amarr_key].stock == 20
    assert hub_state[amarr_key].on_market == 12
