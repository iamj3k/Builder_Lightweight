from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .build_plan import STATIC_BUILD_QUANTITIES

# Canonical blueprint whitelist for fast local validation.
ALLOWED_BLUEPRINT_IDS: set[int] = set()
ALLOWED_BLUEPRINT_NAMES: set[str] = set(STATIC_BUILD_QUANTITIES) | {"Rifter", "Merlin"}

# Per-blueprint efficiency assumptions.
BLUEPRINT_ME_TE: dict[str, dict[str, int]] = {
    bp_name: {"me": 10, "te": 20} for bp_name in ALLOWED_BLUEPRINT_NAMES
}

# Structure/rig bonuses used by local costing assumptions.
STRUCTURE_MANUFACTURING_BONUSES: dict[str, dict[str, float]] = {
    "Azbel": {
        "manufacturing_cost_reduction": 0.01,
        "rig_material_efficiency_bonus": 0.042,
        "rig_time_efficiency_bonus": 0.20,
    },
    "Sotiyo": {
        "manufacturing_cost_reduction": 0.05,
        "rig_material_efficiency_bonus": 0.0,
        "rig_time_efficiency_bonus": 0.30,
    },
    "Tatara": {
        "manufacturing_cost_reduction": 0.0,
        "rig_material_efficiency_bonus": 0.0,
        "rig_time_efficiency_bonus": 0.0,
    },
}

RIG_BONUSES: dict[str, dict[str, float]] = {
    "No rig": {"material_efficiency_bonus": 0.0, "time_efficiency_bonus": 0.0},
    "T2 industry rig": {"material_efficiency_bonus": 0.042, "time_efficiency_bonus": 0.24},
    "T2 reaction rig": {"material_efficiency_bonus": 0.024, "time_efficiency_bonus": 0.24},
}

# Simplified system cost index assumptions.
SYSTEM_INDEX_ASSUMPTIONS: dict[str, float] = {
    "Jita": 0.14,
    "Amarr": 0.10,
    "Dodixie": 0.08,
    "O-PNSN": 0.06,
    "C-N4OD": 0.06,
}

# Tax assumptions and facility profile.
TAX_ASSUMPTIONS: dict[str, float] = {
    "scc_surcharge": 0.04,
    "facility_tax": 0.04,
    "total_tax_rate": 0.08,
}

FACILITY_PROFILE: dict[str, Any] = {
    "name": "Azbel Standard Manufacturing",
    "structure": "Azbel",
    "owner_tax_rate": TAX_ASSUMPTIONS["facility_tax"],
    "scc_surcharge": TAX_ASSUMPTIONS["scc_surcharge"],
}


@dataclass(frozen=True)
class BuildCalculationProfile:
    base_me: int
    base_te: int
    system: str
    system_cost_index: float
    facility_tax_percent: float
    scc_surcharge_percent: float
    additional_cost_isk: float
    runs_per_bpc: str
    calculate_reaction_jobs: bool
    show_detailed_build_steps: bool
    manufacturing_structure: str
    manufacturing_rig: str
    reaction_structure: str
    reaction_rig: str
    manufacturing_material_efficiency_bonus: float
    reaction_material_efficiency_bonus: float


def load_build_calculation_profile(config_defaults: dict[str, Any]) -> BuildCalculationProfile:
    """Build a normalized profile for cost calculations from app defaults."""
    calculation = config_defaults.get("build_calculation", {})

    base_me = int(calculation.get("base_me", config_defaults.get("me", 10)))
    base_te = int(calculation.get("base_te", config_defaults.get("te", 20)))
    system = str(calculation.get("system", config_defaults.get("system", "Jita")))

    manufacturing_structure = str(calculation.get("manufacturing_structure", config_defaults.get("structure", "Azbel")))
    manufacturing_rig = str(calculation.get("manufacturing_rig", "No rig"))
    reaction_structure = str(calculation.get("reaction_structure", "Tatara"))
    reaction_rig = str(calculation.get("reaction_rig", "No rig"))

    manufacturing_structure_bonus = STRUCTURE_MANUFACTURING_BONUSES.get(manufacturing_structure, {})
    manufacturing_rig_bonus = RIG_BONUSES.get(manufacturing_rig, {})
    reaction_rig_bonus = RIG_BONUSES.get(reaction_rig, {})

    return BuildCalculationProfile(
        base_me=base_me,
        base_te=base_te,
        system=system,
        system_cost_index=float(SYSTEM_INDEX_ASSUMPTIONS.get(system, 0.0)),
        facility_tax_percent=float(calculation.get("facility_tax_percent", config_defaults.get("tax_rate", 0.0))),
        scc_surcharge_percent=float(calculation.get("scc_surcharge_percent", TAX_ASSUMPTIONS["scc_surcharge"])),
        additional_cost_isk=float(calculation.get("additional_cost_isk", 0.0)),
        runs_per_bpc=str(calculation.get("runs_per_bpc", "max")),
        calculate_reaction_jobs=bool(calculation.get("calculate_reaction_jobs", False)),
        show_detailed_build_steps=bool(calculation.get("show_detailed_build_steps", False)),
        manufacturing_structure=manufacturing_structure,
        manufacturing_rig=manufacturing_rig,
        reaction_structure=reaction_structure,
        reaction_rig=reaction_rig,
        manufacturing_material_efficiency_bonus=float(
            manufacturing_structure_bonus.get("rig_material_efficiency_bonus", 0.0)
        ) + float(manufacturing_rig_bonus.get("material_efficiency_bonus", 0.0)),
        reaction_material_efficiency_bonus=float(reaction_rig_bonus.get("material_efficiency_bonus", 0.0)),
    )

OUTPUT_MARKET_HUBS: list[str] = ["Jita", "Amarr", "Dodixie", "O-PNSN", "C-N4OD"]

# ESI location-id mapping used to derive CSV hub columns:
# - ESI market orders (volume_remain) in a hub's location IDs -> *_on_market
# - ESI assets (quantity) in a hub's location IDs -> *_stock
#
# If a hub lists multiple location IDs, quantities are summed across every configured location.
MARKET_HUB_LOCATION_IDS: dict[str, list[int]] = {
    "Jita": [
        60003760,      # Jita IV - Moon 4 - Caldari Navy Assembly Plant (NPC station)
        1022734985679,  # Perimeter - Tranquility Trading Tower (player structure)
    ],
    "Amarr": [60008494],      # Amarr VIII (Oris) - Emperor Family Academy
    "Dodixie": [60011866],    # Dodixie IX - Moon 20 - Federation Navy Assembly Plant
    "O-PNSN": [1036927076065],
    "C-N4OD": [1037131880317],
}


def ensure_blueprint_whitelisted(blueprint: dict[str, Any]) -> None:
    """Reject any blueprint not present in the local whitelist."""
    bp_name = str(blueprint.get("name", "")).strip()
    bp_id = blueprint.get("id")

    allowed_by_name = bp_name in ALLOWED_BLUEPRINT_NAMES
    allowed_by_id = isinstance(bp_id, int) and bp_id in ALLOWED_BLUEPRINT_IDS

    if not (allowed_by_name or allowed_by_id):
        raise ValueError(
            f"Blueprint '{bp_name or bp_id}' is not whitelisted; refusing runtime calculation."
        )


def get_me_te_for_blueprint(blueprint_name: str, default_me: int, default_te: int) -> tuple[int, int]:
    profile = BLUEPRINT_ME_TE.get(blueprint_name)
    if not profile:
        return default_me, default_te
    return int(profile["me"]), int(profile["te"])
