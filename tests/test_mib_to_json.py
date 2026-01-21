"""Tests for mib_to_json module."""

import json
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from typing import Any


import pytest
from pytest_mock import MockerFixture

# Add parent directory to path to import from tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.mib_to_json import extract_mib_info, main


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create and clean up a temporary directory."""
    test_dir = tempfile.mkdtemp()
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


@pytest.fixture(autouse=True)
def cleanup_test_json() -> Generator[None, None, None]:
    """Clean up any generated JSON files in mock-behaviour directory."""
    yield
    if os.path.exists('mock-behaviour'):
        for f in os.listdir('mock-behaviour'):
            if f.endswith('_behaviour.json') and f.startswith('TEST-'):
                try:
                    os.remove(os.path.join('mock-behaviour', f))
                except OSError:
                    pass


def test_extract_mib_info_with_real_mib() -> None:
    """Test extract_mib_info with a real compiled MIB."""
    compiled_mibs_location = 'compiled-mibs'
    mib_path = os.path.join(compiled_mibs_location, 'MY-AGENT-MIB.py')
    if not os.path.exists(mib_path):
        pytest.skip("MY-AGENT-MIB.py not found")

    result = extract_mib_info(mib_path, 'MY-AGENT-MIB')

    assert isinstance(result, dict)

    for _symbol_name, symbol_data in result.items():
        assert 'oid' in symbol_data
        assert 'type' in symbol_data
        assert 'access' in symbol_data
        assert 'initial' in symbol_data
        assert 'dynamic_function' in symbol_data
        assert symbol_data['initial'] is None
        assert symbol_data['dynamic_function'] is None


def test_extract_mib_info_with_mock(mocker: MockerFixture) -> None:
    """Test extract_mib_info with mocked MIB builder."""
    mock_symbol = mocker.MagicMock()
    mock_symbol.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
    mock_syntax = mocker.MagicMock()
    mock_syntax.__class__.__name__ = 'OctetString'
    mock_symbol.getSyntax.return_value = mock_syntax
    mock_symbol.getMaxAccess.return_value = 'read-only'

    MockBuilder = mocker.patch('tools.mib_to_json.builder.MibBuilder')
    mock_builder = MockBuilder.return_value
    mock_builder.mibSymbols = {
        'TEST-MIB': {'testScalar': mock_symbol}
    }

    result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')

    assert 'testScalar' in result
    assert result['testScalar']['oid'] == (1, 3, 6, 1, 4, 1, 99999, 1, 0)
    assert result['testScalar']['type'] == 'OctetString'
    assert result['testScalar']['access'] == 'read-only'


def test_extract_mib_info_filters_non_scalars(mocker: MockerFixture) -> None:
    """Test that extract_mib_info only processes objects with getName and getSyntax."""
    mock_valid = mocker.MagicMock()
    mock_valid.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
    mock_syntax = mocker.MagicMock()
    mock_syntax.__class__.__name__ = 'Integer32'
    mock_valid.getSyntax.return_value = mock_syntax
    mock_valid.getMaxAccess.return_value = 'read-write'

    mock_invalid = mocker.MagicMock(spec=[])  # No getName or getSyntax

    MockBuilder = mocker.patch('tools.mib_to_json.builder.MibBuilder')
    mock_builder = MockBuilder.return_value
    mock_builder.mibSymbols = {
        'TEST-MIB': {
            'validScalar': mock_valid,
            'invalidObject': mock_invalid
        }
    }

    result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')

    assert 'validScalar' in result
    assert 'invalidObject' not in result


def test_extract_mib_info_handles_missing_getMaxAccess(mocker: MockerFixture) -> None:
    """Test that extract_mib_info handles symbols without getMaxAccess."""
    mock_symbol = mocker.MagicMock()
    mock_symbol.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
    mock_syntax = mocker.MagicMock()
    mock_syntax.__class__.__name__ = 'Counter32'
    mock_symbol.getSyntax.return_value = mock_syntax
    del mock_symbol.getMaxAccess

    MockBuilder = mocker.patch('tools.mib_to_json.builder.MibBuilder')
    mock_builder = MockBuilder.return_value
    mock_builder.mibSymbols = {
        'TEST-MIB': {'testCounter': mock_symbol}
    }

    result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')

    assert 'testCounter' in result
    assert result['testCounter']['access'] == 'unknown'


def test_main_success(mocker: MockerFixture) -> None:
    """Test main function with valid arguments."""
    mocker.patch('sys.argv', ['mib_to_json.py', 'mibs/MY-AGENT-MIB.py', 'MY-AGENT-MIB'])
    if not os.path.exists('mibs/MY-AGENT-MIB.py'):
        pytest.skip("MY-AGENT-MIB.py not found")

    mock_print = mocker.patch('builtins.print')
    main()

    json_path = 'mock-behaviour/MY-AGENT-MIB_behaviour.json'
    assert os.path.exists(json_path)

    with open(json_path, 'r') as f:
        data: Any = json.load(f)
        assert isinstance(data, dict)

    mock_print.assert_called_once()
    assert 'mock-behaviour/MY-AGENT-MIB_behaviour.json' in mock_print.call_args[0][0]


def test_main_as_script(mocker: MockerFixture) -> None:
    """Test running main when file is executed as __main__."""
    if not os.path.exists('mibs/MY-AGENT-MIB.py'):
        pytest.skip("MY-AGENT-MIB.py not found")

    mocker.patch('sys.argv', ['mib_to_json.py', 'mibs/MY-AGENT-MIB.py', 'MY-AGENT-MIB'])
    mocker.patch('builtins.print')
    from tools import mib_to_json
    assert hasattr(mib_to_json, 'main')


def test_main_insufficient_args(mocker: MockerFixture) -> None:
    """Test main function with insufficient arguments."""
    mock_exit = mocker.patch('sys.exit')
    mocker.patch('sys.argv', ['mib_to_json.py'])
    mock_exit.side_effect = SystemExit(1)
    mock_print = mocker.patch('builtins.print')
    with pytest.raises(SystemExit):
        main()
    mock_print.assert_called_once()
    assert 'Usage:' in mock_print.call_args[0][0]
    mock_exit.assert_called_once_with(1)


def test_main_one_arg(mocker: MockerFixture) -> None:
    """Test main function with only one argument."""
    mock_exit = mocker.patch('sys.exit')
    mocker.patch('sys.argv', ['mib_to_json.py', 'arg1'])
    mock_exit.side_effect = SystemExit(1)
    mock_print = mocker.patch('builtins.print')
    with pytest.raises(SystemExit):
        main()
    mock_print.assert_called_once()
    assert 'Usage:' in mock_print.call_args[0][0]
    mock_exit.assert_called_once_with(1)

