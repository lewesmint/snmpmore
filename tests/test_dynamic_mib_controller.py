"""Tests for DynamicMibController class."""

import os
import sys
import threading
from typing import Any, cast

import pytest

from pysnmp.smi import builder
from pyasn1.type.univ import OctetString
from pytest_mock import MockerFixture

# Add parent directory to path to import from tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dynamic_mib_controller import DynamicMibController


@pytest.fixture
def mib_builder() -> builder.MibBuilder:
    """Create a MibBuilder with SNMPv2-SMI loaded."""
    mib_builder = builder.MibBuilder()
    mib_builder.load_modules('SNMPv2-SMI')
    return mib_builder


@pytest.fixture
def controller(mib_builder: builder.MibBuilder) -> DynamicMibController:
    """Create a DynamicMibController instance."""
    return DynamicMibController(mib_builder)


def test_init(controller: DynamicMibController) -> None:
    """Test DynamicMibController initialization."""
    assert controller.MibScalarInstance is not None
    assert controller.counter == 0
    assert controller.counter_lock is not None
    assert len(controller.table_rows) == 3

    # Verify default table rows
    assert controller.table_rows[0] == [1, 'sensor_a', 25, 'ok']
    assert controller.table_rows[1] == [2, 'sensor_b', 30, 'ok']
    assert controller.table_rows[2] == [3, 'sensor_c', 45, 'warning']


def test_register_scalars(controller: DynamicMibController, mib_builder: builder.MibBuilder, mocker: MockerFixture) -> None:
    """Test register_scalars method."""
    mock_export = mocker.patch.object(mib_builder, 'export_symbols')
    controller.register_scalars(mib_builder)
    mock_export.assert_called_once()
    call_args = mock_export.call_args[0]
    assert call_args[0] == '__MY_MIB'
    assert len(call_args) - 1 == 3  # 3 scalar instances


def test_register_table(controller: DynamicMibController, mib_builder: builder.MibBuilder, mocker: MockerFixture) -> None:
    """Test register_table method."""
    mock_export = mocker.patch.object(mib_builder, 'export_symbols')
    controller.register_table(mib_builder)
    assert mock_export.call_count == 3  # One call per row
    for call in mock_export.call_args_list:
        assert call[0][0] == '__MY_MIB'
        assert len(call[0]) - 1 == 4  # 4 columns per row


def test_update_table(controller: DynamicMibController) -> None:
    """Test update_table method."""
    new_rows = [
        [1, 'new_sensor_1', 100, 'critical'],
        [2, 'new_sensor_2', 50, 'warning']
    ]

    controller.update_table(new_rows)

    assert len(controller.table_rows) == 2
    assert controller.table_rows[0] == [1, 'new_sensor_1', 100, 'critical']
    assert controller.table_rows[1] == [2, 'new_sensor_2', 50, 'warning']


def test_update_table_empty(controller: DynamicMibController) -> None:
    """Test update_table with empty list."""
    controller.update_table([])

    assert len(controller.table_rows) == 0


def test_counter_thread_safety(controller: DynamicMibController) -> None:
    """Test that counter operations are thread-safe."""
    def increment_counter() -> None:
        for _ in range(100):
            with controller.counter_lock:
                controller.counter += 1

    threads = []
    for _ in range(10):
        t = threading.Thread(target=increment_counter)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert controller.counter == 1000  # 10 threads * 100 increments


def test_table_rows_structure(controller: DynamicMibController) -> None:
    """Test that table rows have correct structure."""
    for row in controller.table_rows:
        assert len(row) == 4
        assert isinstance(row[0], int)   # index
        assert isinstance(row[1], str)   # name
        assert isinstance(row[2], int)   # value
        assert isinstance(row[3], str)   # status


def test_mib_scalar_instance_type(controller: DynamicMibController) -> None:
    """Test that MibScalarInstance is correctly imported."""
    scalar = controller.MibScalarInstance(
        (1, 3, 6, 1, 4, 1, 99999, 1, 0),
        (),
        OctetString('test')
    )
    assert scalar is not None


def test_register_scalars_with_real_builder(
    controller: DynamicMibController,
    mib_builder: builder.MibBuilder
) -> None:
    """Test register_scalars with a real MibBuilder."""
    controller.register_scalars(mib_builder)
    assert '__MY_MIB' in cast(dict[Any, Any], mib_builder.mibSymbols)


def test_register_table_with_real_builder(
    controller: DynamicMibController,
    mib_builder: builder.MibBuilder
) -> None:
    """Test register_table with a real MibBuilder."""
    controller.register_table(mib_builder)
    assert '__MY_MIB' in cast(dict[Any, Any], mib_builder.mibSymbols)


def test_update_table_preserves_structure(controller: DynamicMibController) -> None:
    """Test that update_table preserves the expected structure."""
    new_rows = [[10, 'test_sensor', 999, 'ok']]

    controller.update_table(new_rows)

    assert controller.table_rows[0][0] == 10
    assert controller.table_rows[0][1] == 'test_sensor'
    assert controller.table_rows[0][2] == 999
    assert controller.table_rows[0][3] == 'ok'

