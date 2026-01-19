#!/usr/bin/env python3
"""
Unit tests for the pysnmp SNMP agent.

These tests verify the agent's internal data structures and logic
without requiring actual SNMP network communication.
"""

import unittest
import os
import sys
from unittest.mock import patch
from pyasn1.type.univ import Integer

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.agent import SNMPAgent, main
from app import agent as agent_module


class TestSNMPAgent(unittest.TestCase):
    """Test the SNMP agent's internal logic and data structures."""

    def setUp(self) -> None:
        """Create a fresh agent instance for each test."""
        self.agent = SNMPAgent(host='127.0.0.1', port=10161)

    def tearDown(self) -> None:
        """Clean up the agent."""
        self.agent.stop()

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_agent_initialization_default_port(self) -> None:
        """Test that agent initializes with default port."""
        agent = SNMPAgent()
        self.assertEqual(agent.host, '127.0.0.1')
        self.assertEqual(agent.port, 10161)
        self.assertEqual(agent.counter, 0)
        self.assertEqual(len(agent.table_rows), 3)
        agent.stop()

    def test_agent_initialization_custom_port(self) -> None:
        """Test that agent initializes with custom host and port."""
        agent = SNMPAgent(host='0.0.0.0', port=10162)
        self.assertEqual(agent.host, '0.0.0.0')
        self.assertEqual(agent.port, 10162)
        agent.stop()

    def test_agent_has_snmp_engine(self) -> None:
        """Test that agent creates an SNMP engine."""
        self.assertIsNotNone(self.agent.snmpEngine)

    def test_agent_has_mib_builder(self) -> None:
        """Test that agent creates a MIB builder."""
        self.assertIsNotNone(self.agent.mibBuilder)

    def test_agent_has_mib_scalar_instance(self) -> None:
        """Test that agent imports MibScalarInstance."""
        self.assertIsNotNone(self.agent.MibScalarInstance)

    # ========================================================================
    # Counter Tests
    # ========================================================================

    def test_counter_initial_value(self) -> None:
        """Test that counter starts at 0."""
        self.assertEqual(self.agent.counter, 0)

    def test_counter_increments(self) -> None:
        """Test that _get_counter increments the counter."""
        val1 = self.agent._get_counter()  # pyright: ignore[reportPrivateUsage]
        val2 = self.agent._get_counter()  # pyright: ignore[reportPrivateUsage]
        val3 = self.agent._get_counter()  # pyright: ignore[reportPrivateUsage]

        self.assertIsInstance(val1, Integer)
        self.assertIsInstance(val2, Integer)
        self.assertIsInstance(val3, Integer)

        self.assertEqual(int(val1), 1)
        self.assertEqual(int(val2), 2)
        self.assertEqual(int(val3), 3)

    def test_counter_thread_safety(self) -> None:
        """Test that counter uses a lock for thread safety."""
        self.assertIsNotNone(self.agent.counter_lock)
        # Verify it's a threading.Lock
        import threading
        self.assertIsInstance(self.agent.counter_lock, type(threading.Lock()))

    # ========================================================================
    # Table Data Tests
    # ========================================================================

    def test_table_has_three_rows(self) -> None:
        """Test that table is initialized with 3 rows."""
        self.assertEqual(len(self.agent.table_rows), 3)

    def test_table_row_structure(self) -> None:
        """Test that each table row has correct structure [idx, name, value, status]."""
        for row in self.agent.table_rows:
            self.assertEqual(len(row), 4)
            self.assertIsInstance(row[0], int)    # index
            self.assertIsInstance(row[1], str)    # name
            self.assertIsInstance(row[2], int)    # value
            self.assertIsInstance(row[3], str)    # status

    def test_table_row1_data(self) -> None:
        """Test row 1 data: [1, 'sensor_a', 25, 'ok']."""
        row = self.agent.table_rows[0]
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 'sensor_a')
        self.assertEqual(row[2], 25)
        self.assertEqual(row[3], 'ok')

    def test_table_row2_data(self) -> None:
        """Test row 2 data: [2, 'sensor_b', 30, 'ok']."""
        row = self.agent.table_rows[1]
        self.assertEqual(row[0], 2)
        self.assertEqual(row[1], 'sensor_b')
        self.assertEqual(row[2], 30)
        self.assertEqual(row[3], 'ok')

    def test_table_row3_data(self) -> None:
        """Test row 3 data: [3, 'sensor_c', 45, 'warning']."""
        row = self.agent.table_rows[2]
        self.assertEqual(row[0], 3)
        self.assertEqual(row[1], 'sensor_c')
        self.assertEqual(row[2], 45)
        self.assertEqual(row[3], 'warning')

    def test_table_sensor_names(self) -> None:
        """Test that all sensor names are correct."""
        names = [row[1] for row in self.agent.table_rows]
        self.assertEqual(names, ['sensor_a', 'sensor_b', 'sensor_c'])

    def test_table_sensor_values(self) -> None:
        """Test that all sensor values are correct."""
        values = [row[2] for row in self.agent.table_rows]
        self.assertEqual(values, [25, 30, 45])

    def test_table_sensor_statuses(self) -> None:
        """Test that all sensor statuses are correct."""
        statuses = [row[3] for row in self.agent.table_rows]
        self.assertEqual(statuses, ['ok', 'ok', 'warning'])

    # ========================================================================
    # Configuration Tests
    # ========================================================================

    def test_transport_configured(self) -> None:
        """Test that transport is configured (no exceptions during init)."""
        # If we got here, _setup_transport() didn't raise an exception
        self.assertTrue(True)

    def test_community_configured(self) -> None:
        """Test that community is configured (no exceptions during init)."""
        # If we got here, _setup_community() didn't raise an exception
        self.assertTrue(True)

    def test_responders_configured(self) -> None:
        """Test that responders are configured (no exceptions during init)."""
        # If we got here, _setup_responders() didn't raise an exception
        self.assertTrue(True)

    def test_mib_objects_registered(self) -> None:
        """Test that MIB objects are registered (no exceptions during init)."""
        # If we got here, _register_mib_objects() didn't raise an exception
        self.assertTrue(True)

    # ========================================================================
    # Data Validation Tests
    # ========================================================================

    def test_all_sensor_values_positive(self) -> None:
        """Test that all sensor values are positive integers."""
        for row in self.agent.table_rows:
            value: int = row[2]  # type: ignore[assignment]
            self.assertGreater(value, 0, "Sensor value should be positive")

    def test_all_sensor_indices_sequential(self) -> None:
        """Test that sensor indices are sequential starting from 1."""
        indices = [row[0] for row in self.agent.table_rows]
        self.assertEqual(indices, [1, 2, 3])

    def test_sensor_status_values_valid(self) -> None:
        """Test that sensor status values are valid strings."""
        valid_statuses = {'ok', 'warning', 'error', 'critical'}
        for row in self.agent.table_rows:
            self.assertIn(row[3], valid_statuses)

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_multiple_agents_different_ports(self) -> None:
        """Test that multiple agents can be created on different ports."""
        agent1 = SNMPAgent(port=10163)
        agent2 = SNMPAgent(port=10164)

        self.assertEqual(agent1.port, 10163)
        self.assertEqual(agent2.port, 10164)
        self.assertEqual(agent1.counter, 0)
        self.assertEqual(agent2.counter, 0)

        # Counters should be independent
        agent1._get_counter()  # pyright: ignore[reportPrivateUsage]
        agent1._get_counter()  # pyright: ignore[reportPrivateUsage]
        agent2._get_counter()  # pyright: ignore[reportPrivateUsage]

        self.assertEqual(agent1.counter, 2)
        self.assertEqual(agent2.counter, 1)

        agent1.stop()
        agent2.stop()

    def test_agent_run_keyboard_interrupt(self) -> None:
        """Test agent run method handles KeyboardInterrupt."""
        agent = SNMPAgent()

        # Mock the dispatcher to raise KeyboardInterrupt
        with patch.object(agent.snmpEngine.transport_dispatcher, 'run_dispatcher') as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            with patch('builtins.print'):  # Suppress print output
                agent.run()

            # Verify run_dispatcher was called
            mock_run.assert_called_once()

        agent.stop()

    def test_main_function(self) -> None:
        """Test the main function creates and runs an agent."""
        with patch.object(agent_module.SNMPAgent, 'run') as mock_run:
            main()
            mock_run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
