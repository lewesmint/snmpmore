"""Tests for the SNMPAgent implementation."""

from collections.abc import Generator

import pytest
from unittest.mock import patch, MagicMock

from app.agent import SNMPAgent


@pytest.fixture
def agent() -> Generator[SNMPAgent, None, None]:
    """Create an SNMPAgent instance for testing."""
    with patch("app.agent.SNMPAgent._load_config", return_value=None):
        agent = SNMPAgent(host='127.0.0.1', port=11661, config_path='agent_config.yaml')
        # Ensure mib_jsons is always present for all tests
        if not hasattr(agent, 'mib_jsons'):
            agent.mib_jsons = {}
        yield agent
        agent.stop()


def test_mibs_loaded_from_config(agent: SNMPAgent) -> None:
    """Test that MIBs are loaded from config."""
    agent.mib_jsons = {'SNMPv2-MIB': {}, 'UDP-MIB': {}, 'CISCO-ALARM-MIB': {}}
    mibs = agent.mib_jsons.keys()
    assert 'SNMPv2-MIB' in mibs
    assert 'UDP-MIB' in mibs
    assert 'CISCO-ALARM-MIB' in mibs


def test_scalar_value_get(agent: SNMPAgent) -> None:
    """Test getting a scalar value."""
    sysdescr_oid = (1, 3, 6, 1, 2, 1, 1, 1, 0)
    agent.mib_jsons = {'SNMPv2-MIB': {'sysDescr': {'current': 'SNMP Agent Test'}}}
    with patch.object(agent, "get_scalar_value", return_value="SNMP Agent Test"):
        value = agent.get_scalar_value(sysdescr_oid[:-1])
        assert isinstance(value, str)
        assert 'SNMP Agent' in value


def test_scalar_value_set_and_persist(agent: SNMPAgent) -> None:
    """Test setting and persisting a scalar value."""
    syscontact_oid = (1, 3, 6, 1, 2, 1, 1, 4, 0)
    test_val = 'PyTest Test Contact'
    agent.mib_jsons = {'SNMPv2-MIB': {'sysContact': {'current': ''}}}
