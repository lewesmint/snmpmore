"""
Tests for the canonical type registry and its integration with the agent.
"""
import os
import json
import pytest
from pathlib import Path
from typing import Any
import builtins
from app.snmp_agent import SNMPAgent
from app.type_registry import TYPE_REGISTRY, export_to_json

def test_type_registry_export_and_json(tmp_path: Path) -> None:
    """Test that the type registry exports correctly to JSON and matches the in-memory registry."""
    out_path = tmp_path / "types.json"
    export_to_json(str(out_path))
    with open(out_path) as f:
        data = json.load(f)
    assert data == TYPE_REGISTRY

def test_type_registry_fields() -> None:
    """Test that all entries in the type registry have required fields and correct types."""
    for oid, entry in TYPE_REGISTRY.items():
        assert isinstance(oid, str)
        assert isinstance(entry, dict)
        assert set(entry.keys()) >= {"name", "syntax", "description"}
        assert isinstance(entry["name"], str)
        assert isinstance(entry["syntax"], str)
        assert isinstance(entry["description"], str)

def test_agent_loads_type_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the agent loads the canonical type registry from types.json."""
    # Patch types.json to a known file
    test_types = {"1.2.3.4.5": {"name": "foo", "syntax": "OctetString", "description": "desc"}}
    test_types_path = tmp_path / "types_test.json"
    with open(test_types_path, "w") as f:
        json.dump(test_types, f)
    orig_open = builtins.open
    def open_patch(path: str, mode: str = 'r', *args: Any, **kwargs: Any) -> object:
        if str(path).endswith("types.json"):
            return orig_open(test_types_path, mode, *args, **kwargs)
        return orig_open(path, mode, *args, **kwargs)
    monkeypatch.setattr("os.path.dirname", lambda _: str(tmp_path))
    monkeypatch.setattr("builtins.open", open_patch)
    agent = SNMPAgent()
    assert agent.type_registry == test_types
