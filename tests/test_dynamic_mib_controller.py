import unittest
import os
import sys
from unittest.mock import patch
from pysnmp.smi import builder
from pyasn1.type.univ import OctetString
from typing import Any, cast

# Add parent directory to path to import from tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dynamic_mib_controller import DynamicMibController


class TestDynamicMibController(unittest.TestCase):
    """Test suite for DynamicMibController class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mibBuilder = builder.MibBuilder()
        # Load SNMPv2-SMI to get MibScalarInstance
        self.mibBuilder.load_modules('SNMPv2-SMI')
        self.controller = DynamicMibController(self.mibBuilder)

    def test_init(self) -> None:
        """Test DynamicMibController initialization."""
        self.assertIsNotNone(self.controller.MibScalarInstance)
        self.assertEqual(self.controller.counter, 0)
        self.assertIsNotNone(self.controller.counter_lock)
        self.assertEqual(len(self.controller.table_rows), 3)
        
        # Verify default table rows
        self.assertEqual(self.controller.table_rows[0], [1, 'sensor_a', 25, 'ok'])
        self.assertEqual(self.controller.table_rows[1], [2, 'sensor_b', 30, 'ok'])
        self.assertEqual(self.controller.table_rows[2], [3, 'sensor_c', 45, 'warning'])

    def test_register_scalars(self) -> None:
        """Test register_scalars method."""
        # Mock the mibBuilder.exportSymbols method
        with patch.object(self.mibBuilder, 'export_symbols') as mock_export:
            self.controller.register_scalars(self.mibBuilder)
            
            # Verify exportSymbols was called
            mock_export.assert_called_once()
            
            # Verify it was called with '__MY_MIB' as first argument
            call_args = mock_export.call_args[0]
            self.assertEqual(call_args[0], '__MY_MIB')
            
            # Verify 3 scalar instances were registered
            # (1 for string, 1 for counter, 1 for gauge)
            self.assertEqual(len(call_args) - 1, 3)

    def test_register_table(self) -> None:
        """Test register_table method."""
        with patch.object(self.mibBuilder, 'export_symbols') as mock_export:
            self.controller.register_table(self.mibBuilder)
            
            # Should be called once for each row (3 rows)
            self.assertEqual(mock_export.call_count, 3)
            
            # Each call should have '__MY_MIB' as first argument
            for call in mock_export.call_args_list:
                self.assertEqual(call[0][0], '__MY_MIB')
                # Each row has 4 columns, so 4 MibScalarInstance objects + 1 for name
                self.assertEqual(len(call[0]) - 1, 4)

    def test_update_table(self) -> None:
        """Test update_table method."""
        new_rows = [
            [1, 'new_sensor_1', 100, 'critical'],
            [2, 'new_sensor_2', 50, 'warning']
        ]
        
        self.controller.update_table(new_rows)
        
        self.assertEqual(len(self.controller.table_rows), 2)
        self.assertEqual(self.controller.table_rows[0], [1, 'new_sensor_1', 100, 'critical'])
        self.assertEqual(self.controller.table_rows[1], [2, 'new_sensor_2', 50, 'warning'])

    def test_update_table_empty(self) -> None:
        """Test update_table with empty list."""
        self.controller.update_table([])
        
        self.assertEqual(len(self.controller.table_rows), 0)

    def test_counter_thread_safety(self) -> None:
        """Test that counter operations are thread-safe."""
        import threading
        
        # Create a simple counter increment function
        def increment_counter() -> None:
            for _ in range(100):
                with self.controller.counter_lock:
                    self.controller.counter += 1
        
        # Run multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment_counter)
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify counter is correct (10 threads * 100 increments)
        self.assertEqual(self.controller.counter, 1000)

    def test_table_rows_structure(self) -> None:
        """Test that table rows have correct structure."""
        for row in self.controller.table_rows:
            self.assertEqual(len(row), 4)
            self.assertIsInstance(row[0], int)  # index
            self.assertIsInstance(row[1], str)  # name
            self.assertIsInstance(row[2], int)  # value
            self.assertIsInstance(row[3], str)  # status

    def test_mib_scalar_instance_type(self) -> None:
        """Test that MibScalarInstance is correctly imported."""
        # Create a simple scalar instance
        scalar = self.controller.MibScalarInstance(
            (1, 3, 6, 1, 4, 1, 99999, 1, 0),
            (),
            OctetString('test')
        )
        
        # Verify it's the correct type
        self.assertIsNotNone(scalar)

    def test_register_scalars_with_real_builder(self) -> None:
        """Test register_scalars with a real MibBuilder."""
        # This test verifies the actual registration works
        self.controller.register_scalars(self.mibBuilder)

        # Verify symbols were exported
        self.assertIn('__MY_MIB', cast(dict[Any, Any], self.mibBuilder.mibSymbols))

    def test_register_table_with_real_builder(self) -> None:
        """Test register_table with a real MibBuilder."""
        # This test verifies the actual registration works
        self.controller.register_table(self.mibBuilder)

        # Verify symbols were exported
        self.assertIn('__MY_MIB', cast(dict[Any, Any], self.mibBuilder.mibSymbols))

    def test_update_table_preserves_structure(self) -> None:
        """Test that update_table preserves the expected structure."""
        new_rows = [
            [10, 'test_sensor', 999, 'ok']
        ]
        
        self.controller.update_table(new_rows)
        
        # Verify the structure is preserved
        self.assertEqual(self.controller.table_rows[0][0], 10)
        self.assertEqual(self.controller.table_rows[0][1], 'test_sensor')
        self.assertEqual(self.controller.table_rows[0][2], 999)
        self.assertEqual(self.controller.table_rows[0][3], 'ok')


if __name__ == '__main__':
    unittest.main()

