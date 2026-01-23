"""Tests for compile_mib module."""

import sys
from collections.abc import Generator
from io import StringIO


import pytest
import pytest_mock

import types
import sys

# Ensure 'tools.compile_mib' exists for import during tests if not present
if 'tools.compile_mib' not in sys.modules:
    sys.modules['tools.compile_mib'] = types.ModuleType('tools.compile_mib')


@pytest.fixture(autouse=True)
def cleanup_compile_mib() -> Generator[None, None, None]:
    """Clean up compile_mib from sys.modules before and after each test."""
    if 'tools.compile_mib' in sys.modules:
        del sys.modules['tools.compile_mib']
    yield
    if 'tools.compile_mib' in sys.modules:
        del sys.modules['tools.compile_mib']



def _import_with_mocks(
    mock_results: dict[str, str], 
    mocker: "pytest_mock.MockerFixture"
) -> str:
    """Helper to import compile_mib with mocked compiler results using pytest-mock."""
    captured_output = StringIO()
    mock_compiler_class = mocker.patch('pysmi.compiler.MibCompiler')
    mock_compiler = mocker.MagicMock()
    mock_compiler_class.return_value = mock_compiler
    mock_compiler.compile.return_value = mock_results
    mocker.patch('sys.stdout', captured_output)
    mocker.patch('sys.stderr', captured_output)
    try:
        __import__("tools.compile_mib")  # noqa: F401
    except SystemExit:
        pass  # Expected for some tests
    return captured_output.getvalue()


def test_compile_mib_success(mocker: pytest_mock.MockerFixture) -> None:
    """Test successful MIB compilation."""
    mock_results = {'CISCO-ALARM-MIB': 'compiled'}
    output = _import_with_mocks(mock_results, mocker)
    assert 'CISCO-ALARM-MIB: compiled' in output


def test_compile_mib_failure(mocker: pytest_mock.MockerFixture) -> None:
    """Test MIB compilation failure."""
    mock_results = {'CISCO-ALARM-MIB': 'failed'}
    output = _import_with_mocks(mock_results, mocker)
    assert 'CISCO-ALARM-MIB: failed' in output


def test_compile_mib_partial_success(mocker: pytest_mock.MockerFixture) -> None:
    """Test MIB compilation with partial success."""
    mock_results = {
        'CISCO-ALARM-MIB': 'compiled',
        'SNMPv2-SMI': 'missing'
    }
    output = _import_with_mocks(mock_results, mocker)
    assert 'CISCO-ALARM-MIB: compiled' in output
    assert 'SNMPv2-SMI: missing' in output
