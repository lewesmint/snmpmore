
import unittest
import os
from app.agent import SNMPAgent

class TestSNMPAgentNew(unittest.TestCase):
	"""Tests for the new SNMPAgent implementation (dynamic MIB/JSON loading)."""

	def setUp(self) -> None:
		# Use a non-standard port to avoid conflicts
		self.agent = SNMPAgent(host='127.0.0.1', port=11661, config_path='agent_config.yaml')

	def tearDown(self) -> None:
		self.agent.stop()

	def test_mibs_loaded_from_config(self) -> None:
		# Should load all MIBs listed in agent_config.yaml
		mibs = self.agent.mib_jsons.keys()
		self.assertIn('SNMPv2-MIB', mibs)
		self.assertIn('UDP-MIB', mibs)
		self.assertIn('CISCO-ALARM-MIB', mibs)

	def test_scalar_value_get(self) -> None:
		# sysDescr OID from SNMPv2-MIB_behaviour.json
		sysdescr_oid = (1,3,6,1,2,1,1,1,0)
		value = self.agent.get_scalar_value(sysdescr_oid[:-1])  # get_scalar_value expects base OID
		self.assertIsInstance(value, str)
		self.assertIn('SNMP Agent', value)

	def test_scalar_value_set_and_persist(self) -> None:
		# sysContact is read-write in SNMPv2-MIB
		syscontact_oid = (1,3,6,1,2,1,1,4,0)
		test_val = 'UnitTest Contact'
		self.agent.set_scalar_value(syscontact_oid[:-1], test_val)
		# Value should be persisted in the agent's in-memory JSON
		mib_json = self.agent.mib_jsons['SNMPv2-MIB']
		self.assertEqual(mib_json['sysContact']['current'], test_val)

	def test_table_registration(self) -> None:
		# UDP-MIB has udpTable and udpEntry, check that table registration does not raise
		# (No exception = pass, as table registration is internal)
		# We can check that the agent's MIB builder has exported UDP-MIB table symbols
		mibBuilder = self.agent.mibBuilder
		# Should not raise
		udpTable = mibBuilder.importSymbols('UDP-MIB', 'udpTable')[0]
		self.assertIsNotNone(udpTable)

	def test_agent_can_be_stopped(self) -> None:
		# Should be able to stop the agent without error
		self.agent.stop()
		self.assertTrue(True)

if __name__ == '__main__':
	unittest.main()
