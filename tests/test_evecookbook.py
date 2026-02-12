import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.evecookbook import EveCookbookClient
from src.engine import CalculatorEngine


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_evecookbook_client_parses_materials(monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: float):
        assert "Rifter" in url
        assert timeout == 15.0
        return _FakeResponse(
            {
                "materials": [
                    {"name": "Tritanium", "quantity": 10, "adjusted_price": 4.2},
                    {"name": "Pyerite", "quantity": 2, "adjusted_price": 8.5},
                ]
            }
        )

    monkeypatch.setattr("src.evecookbook.urlopen", fake_urlopen)

    client = EveCookbookClient(
        {
            "enabled": True,
            "base_url": "https://example.test",
            "blueprint_endpoint": "/api/blueprints/{blueprint_name}",
            "request_timeout_s": 15,
        }
    )
    result = client.fetch_blueprint("Rifter")

    assert result.name == "Rifter"
    assert result.materials == {"Tritanium": 10.0, "Pyerite": 2.0}
    assert result.material_prices == {"Tritanium": 4.2, "Pyerite": 8.5}


def test_engine_can_hydrate_blueprints_from_evecookbook(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {"me": 10, "te": 20, "tax_rate": 0.08},
                "evecookbook": {
                    "enabled": True,
                    "base_url": "https://example.test",
                    "blueprint_endpoint": "/api/blueprints/{blueprint_name}",
                    "blueprints": ["Rifter"],
                },
                "price_overrides": {},
                "blueprints": [],
            }
        ),
        encoding="utf-8",
    )

    def fake_urlopen(url: str, timeout: float):
        return _FakeResponse(
            {
                "materials": [
                    {"name": "Tritanium", "quantity": 100, "adjusted_price": 1.0},
                    {"name": "Pyerite", "quantity": 10, "adjusted_price": 2.0},
                ]
            }
        )

    monkeypatch.setattr("src.evecookbook.urlopen", fake_urlopen)

    engine = CalculatorEngine(config_path)
    result = engine.refresh_data()

    assert len(result) == 1
    assert result[0].name == "Rifter"
    assert result[0].total_cost > 0


def test_engine_falls_back_to_local_blueprints_when_cookbook_hydration_fails(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {"me": 10, "te": 20, "tax_rate": 0.08},
                "evecookbook": {
                    "enabled": True,
                    "base_url": "https://example.test",
                    "blueprint_endpoint": "/api/blueprints/{blueprint_name}",
                    "blueprints": ["Rifter"],
                },
                "price_overrides": {"Tritanium": 2.0},
                "blueprints": [{"name": "Rifter", "materials": {"Tritanium": 10}}],
            }
        ),
        encoding="utf-8",
    )

    def failing_urlopen(url: str, timeout: float):
        raise RuntimeError("cookbook unavailable")

    monkeypatch.setattr("src.evecookbook.urlopen", failing_urlopen)

    engine = CalculatorEngine(config_path)
    result = engine.refresh_data()

    assert len(result) == 1
    assert result[0].name == "Rifter"
    assert result[0].total_cost > 0
