"""Tests for table registration in SNMPAgent."""



import pytest
from app.snmp_agent import SNMPAgent
from typing import Generator, Any
from pytest_mock import MockerFixture


@pytest.fixture
def agent(mocker: MockerFixture) -> SNMPAgent:
    """Create a mocked SNMPAgent for testing."""
    agent = SNMPAgent.__new__(SNMPAgent)
    agent.mibBuilder = mocker.MagicMock()
    agent.mibBuilder.import_symbols.return_value = []
    agent.snmpEngine = mocker.MagicMock()
    # Patch SNMPAgent dependencies for table registration
    agent.MibTable = mocker.MagicMock()
    agent.MibTableRow = mocker.MagicMock()
    agent.MibTableColumn = mocker.MagicMock()
    agent.MibScalar = mocker.MagicMock()
    return agent




@pytest.fixture
def mock_context(mocker: MockerFixture) -> Generator[Any, None, None]:
    """Mock the SnmpContext using pytest-mock."""
    mock = mocker.patch('app.agent.context.SnmpContext')
    mock.return_value.get_mib_instrum.return_value = mocker.MagicMock()
    yield mock


@pytest.fixture
def mock_agent_methods(agent: SNMPAgent, mocker: MockerFixture) -> Generator[None, None, None]:
    """Mock internal agent methods using pytest-mock."""
    mocker.patch.object(agent, '_get_pysnmp_type_from_info', return_value=int)
    mocker.patch.object(agent, '_get_snmp_value', return_value=1)
    yield


def test_single_column_index(agent: SNMPAgent, mock_context: Any, mock_agent_methods: None) -> None:  # noqa: ARG001
    """Test table registration with a single column index."""
    table_data = {
        'table': {'oid': [1, 3, 6, 1, 2, 1, 2, 2]},
        'entry': {'oid': [1, 3, 6, 1, 2, 1, 2, 2, 1]},
        'columns': {
            'ifIndex': {'oid': [1, 3, 6, 1, 2, 1, 2, 2, 1, 1], 'type': 'Integer32', 'access': 'not-accessible'},
            'ifDescr': {'oid': [1, 3, 6, 1, 2, 1, 2, 2, 1, 2], 'type': 'OctetString', 'access': 'read-only'}
        },
        'prefix': 'ifTable'
    }
    agent._register_single_table('IF-MIB', 'ifTable', table_data, {})


def test_augments_inherited_index(agent: SNMPAgent, mock_context: Any, mock_agent_methods: None) -> None:  # noqa: ARG001
    """Test table registration with AUGMENTS inherited index."""
    table_data = {
        'table': {'oid': [1, 3, 6, 1, 2, 1, 31, 1, 1]},
        'entry': {'oid': [1, 3, 6, 1, 2, 1, 31, 1, 1, 1], 'index_from': [('IF-MIB', 'ifEntry', 'ifIndex')]},
        'columns': {
            'ifIndex': {'oid': [1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 1], 'type': 'Integer32', 'access': 'not-accessible'},
            'ifName': {'oid': [1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 2], 'type': 'OctetString', 'access': 'read-only'}
        },
        'prefix': 'ifXTable'
    }
    agent._register_single_table('IF-MIB', 'ifXTable', table_data, {})


def test_multi_column_index_inherited_and_local(agent: SNMPAgent, mock_context: Any, mock_agent_methods: None) -> None:  # noqa: ARG001
    """Test table registration with multi-column index (inherited + local)."""
    table_data = {
        'table': {'oid': [1, 3, 6, 1, 2, 1, 31, 4]},
        'entry': {'oid': [1, 3, 6, 1, 2, 1, 31, 4, 1], 'index_from': [('IF-MIB', 'ifEntry', 'ifIndex')]},
        'columns': {
            'ifIndex': {'oid': [1, 3, 6, 1, 2, 1, 31, 4, 1, 1], 'type': 'Integer32', 'access': 'not-accessible'},
            'ifRcvAddressType': {'oid': [1, 3, 6, 1, 2, 1, 31, 4, 1, 2], 'type': 'Integer32', 'access': 'not-accessible'},
            'ifRcvAddress': {'oid': [1, 3, 6, 1, 2, 1, 31, 4, 1, 3], 'type': 'PhysAddress', 'access': 'not-accessible'},
            'ifRcvAddressStatus': {'oid': [1, 3, 6, 1, 2, 1, 31, 4, 1, 4], 'type': 'Integer32', 'access': 'read-only'}
        },
        'prefix': 'ifRcvAddressTable'
    }
    agent._register_single_table('IF-MIB', 'ifRcvAddressTable', table_data, {})
