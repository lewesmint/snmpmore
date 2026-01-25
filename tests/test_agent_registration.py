
import pytest
from pytest_mock import MockerFixture
from typing import Optional, Any

from app.snmp_agent import SNMPAgent

class DummyAppConfig:
    def __init__(self, mibs: list[str]) -> None:
        self._mibs = mibs

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if key == 'mibs':
            return self._mibs
        return default

    def get_platform_setting(self, key: str, default: object = None) -> object:
        return default

def test_register_mib_objects_handles_tcs(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, mocker: MockerFixture) -> None:
    # Minimal MIB JSON with a TC and a base type
    mib_json = {
        "ifName": {
            "oid": [1,3,6,1,2,1,31,1,1,1,1],
            "type": "DisplayString",
            "access": "read-only",
            "initial": "eth0"
        },
        "ifIndex": {
            "oid": [1,3,6,1,2,1,2,2,1,1],
            "type": "Integer32",
            "access": "read-only",
            "initial": 1
        }
    }
    # Patch methods that interact with SNMP engine and file system
    monkeypatch.setattr(SNMPAgent, "_setup_transport", lambda self: None)
    monkeypatch.setattr(SNMPAgent, "_setup_community", lambda self: None)
    monkeypatch.setattr(SNMPAgent, "_setup_responders", lambda self: None)
    monkeypatch.setattr(SNMPAgent, "_load_config_and_prepare_mibs", lambda self: None)
    # Create agent and inject dummy MIB JSON
    agent = SNMPAgent(config_path="dummy.yaml")
    agent.app_config = DummyAppConfig(["IF-MIB"])  # type: ignore[assignment]
    agent.mib_jsons = {"IF-MIB": mib_json}
    # Patch registration methods to just record calls using monkeypatch
    scalars_mock = mocker.Mock()
    tables_mock = mocker.Mock()
    monkeypatch.setattr(agent, "_register_scalars", scalars_mock)
    monkeypatch.setattr(agent, "_register_tables", tables_mock)
    # Call the method under test
    agent._register_mib_objects()
    # Check that registration was called with correct arguments
    scalars_mock.assert_called_with(
        "IF-MIB", mib_json, agent._find_table_related_objects(mib_json),
        {'TestAndIncr': agent.TestAndIncr, 'RowStatus': agent.RowStatus}
    )
    tables_mock.assert_called_with(
        "IF-MIB", mib_json, {'TestAndIncr': agent.TestAndIncr, 'RowStatus': agent.RowStatus}
    )
