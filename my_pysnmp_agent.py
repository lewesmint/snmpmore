#!/usr/bin/env python3
"""
SNMP agent using pysnmp that exposes scalars and tables as defined in MY-AGENT-MIB.
Listens on UDP port 10161 (non-privileged) and responds to SNMP queries.
"""

import threading
import asyncio
import time
import logging
import os
import yaml
import json
from typing import Any, Tuple, List, cast
from mib_compiler import MibCompiler
from behavior_generator import BehaviorGenerator
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.smi import builder
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.proto.api import v2c
from pyasn1.type.univ import OctetString, Integer, ObjectIdentifier
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, NotificationType, send_notification
)
from pysnmp.smi.rfc1902 import ObjectIdentity

# Import SNMP data types
Counter32 = v2c.Counter32
Counter64 = v2c.Counter64
Gauge32 = v2c.Gauge32
TimeTicks = v2c.TimeTicks
IpAddress = v2c.IpAddress
Unsigned32 = v2c.Unsigned32
Integer32 = v2c.Integer32

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



class SNMPAgent:
    """SNMP Agent that serves enterprise MIB data."""

    def get_scalar_value(self, oid: Tuple[int, ...]) -> str:
        # Find the MibScalarInstance for the given OID and return its value as string
        mibInstrum = context.SnmpContext(self.snmpEngine).get_mib_instrum()
        var_binds = mibInstrum.read_variables((oid, None))
        # Return the value as string
        # var_binds is a sequence of (name, value) tuples
        value = cast(Any, var_binds[0][1])
        return str(value)

    def set_scalar_value(self, oid: Tuple[int, ...], value: str) -> None:
        # Find the MibScalarInstance for the given OID and set its value (as OctetString)
        mibInstrum = context.SnmpContext(self.snmpEngine).get_mib_instrum()
        mibInstrum.write_variables((oid, OctetString(value)))

    def __init__(self, host: str = '127.0.0.1', port: int = 161, config_path: str = 'agent_config.yaml') -> None:
        """Initialize the SNMP agent with config file support.

        Args:
            host: IP address to bind to
            port: UDP port to listen on (default 10161 for non-root)
            config_path: Path to YAML config listing MIBs
        """
        self.host = host
        self.port = port
        self.snmpEngine = engine.SnmpEngine()
        self.mibBuilder = self.snmpEngine.get_mib_builder()

        # Add MIB sources
        self.mibBuilder.add_mib_sources(builder.DirMibSource('./compiled-mibs'))

        # Import MIB classes from SNMPv2-SMI
        (self.MibScalar,
         self.MibScalarInstance,
         self.MibTable,
         self.MibTableRow,
         self.MibTableColumn) = self.mibBuilder.import_symbols(
            'SNMPv2-SMI',
            'MibScalar',
            'MibScalarInstance',
            'MibTable',
            'MibTableRow',
            'MibTableColumn'
        )

        # Counter for dynamic scalar
        self.counter = 0
        self.counter_lock = threading.Lock()

        # Start time for TimeTicks
        self.start_time = time.time()

        # Table data
        self.table_rows = [
            [1, 'sensor_a', 25, 'ok'],
            [2, 'sensor_b', 30, 'ok'],
            [3, 'sensor_c', 45, 'warning'],
        ]

        # Load config and ensure MIBs/JSONs exist
        self.mib_jsons: dict[str, Any] = {}
        self._load_config_and_prepare_mibs(config_path)

        self._setup_transport()
        self._setup_community()
        self._setup_responders()
        self._register_mib_objects()

    def _load_config_and_prepare_mibs(self, config_path: str) -> None:
        """Load config YAML, ensure compiled MIBs and JSONs exist, generate if missing, using runtime classes."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found")
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        mibs: List[str] = config_data.get('mibs', [])
        mib_compiler = MibCompiler()
        behavior_gen = BehaviorGenerator()
        for mib in mibs:
            mib_txt = None
            # Try to find the .txt in data/mibs/Fake or data/mibs/Palo Alto Networks
            for d in ['data/mibs/Fake', 'data/mibs/Palo Alto Networks']:
                candidate = os.path.join(d, f'{mib}.txt')
                if os.path.exists(candidate):
                    mib_txt = candidate
                    break
            if not mib_txt:
                raise FileNotFoundError(f"MIB source for {mib} not found")
            compiled_py = mib_compiler.compile(mib_txt)
            json_path = behavior_gen.generate(compiled_py, mib)
            with open(json_path, 'r') as jf:
                self.mib_jsons[mib] = json.load(jf)

    def _setup_transport(self) -> None:
        """Configure UDP transport."""
        config.add_transport(
            self.snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode((self.host, self.port))
        )

    def _setup_community(self) -> None:
        """Configure SNMPv2c community."""
        config.add_v1_system(self.snmpEngine, 'my-area', 'public')

        # Allow access to the standard SNMP system group subtree
        config.add_vacm_user(
            self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
            (1, 3, 6, 1, 2, 1, 1)
        )
        # Also allow full access to enterprise subtree
        config.add_vacm_user(
            self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
            (1, 3, 6, 1, 4, 1, 99999)
        )


    def _setup_responders(self) -> None:
        """Setup SNMP command responders."""
        snmpContext = context.SnmpContext(self.snmpEngine)
        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.SetCommandResponder(self.snmpEngine, snmpContext)

    def _get_counter(self, *args: Any) -> Integer:
        """Dynamic counter that increments on each GET."""
        with self.counter_lock:
            self.counter += 1
            return Integer(self.counter)

    def _register_mib_objects(self) -> None:
        """Register all MIB objects (scalars and tables) for all MIBs in config."""
        type_map = {
            'DisplayString': OctetString,
            'Integer32': Integer32,
            'Counter32': Counter32,
            'Counter64': Counter64,
            'Gauge32': Gauge32,
            'TimeTicks': TimeTicks,
            'IpAddress': IpAddress,
            'Unsigned32': Unsigned32,
            'OctetString': OctetString,
            'Integer': Integer,
        }

        # Add RFC SNMPv2-MIB system group scalars (always present)
        rfc_scalars = [
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 1), OctetString()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 1), (0,), OctetString('Simple Python SNMP Agent - Demo System'))),
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 2), ObjectIdentifier()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 2), (0,), ObjectIdentifier('1.3.6.1.4.1.99999'))),
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 3), Integer()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 3), (0,), Integer(int(time.time() * 100)))),
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 4), OctetString()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 4), (0,), OctetString('Admin <admin@example.com>'))),
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 5), OctetString()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 5), (0,), OctetString('my-pysnmp-agent'))),
            (self.MibScalar((1, 3, 6, 1, 2, 1, 1, 6), OctetString()),
             self.MibScalarInstance((1, 3, 6, 1, 2, 1, 1, 6), (0,), OctetString('Development Lab'))),
        ]
        for pair in rfc_scalars:
            self.mibBuilder.export_symbols('__MY_MIB', *pair)

        # Register all MIBs from config
        for mib, mib_json in self.mib_jsons.items():
            # Scalars
            scalar_symbols: list[Any] = []
            for name, info in mib_json.items():
                oid_value = cast(List[int], info['oid']) if isinstance(info['oid'], list) else []
                if info['type'] in type_map and isinstance(info['oid'], list) and len(oid_value) == 8:
                    pysnmp_type = type_map[info['type']]
                    scalar_oid = tuple(oid_value)
                    initial = info.get('initial')
                    if initial is not None:
                        value = pysnmp_type(initial)
                    else:
                        if pysnmp_type is OctetString:
                            value = OctetString('default')
                        elif pysnmp_type is Integer32 or pysnmp_type is Integer:
                            value = pysnmp_type(0)
                        elif pysnmp_type in (Counter32, Counter64, Gauge32, Unsigned32):
                            value = pysnmp_type(0)
                        elif pysnmp_type is IpAddress:
                            value = IpAddress('127.0.0.1')
                        elif pysnmp_type is TimeTicks:
                            value = TimeTicks(0)
                        else:
                            value = pysnmp_type()
                    scalar_symbols.append(self.MibScalar(scalar_oid, pysnmp_type()))
                    scalar_symbols.append(self.MibScalarInstance(scalar_oid, (0,), value))
            if scalar_symbols:
                self.mibBuilder.export_symbols(f'__{mib}', *scalar_symbols)

            # Table support (if present)
            table_info = {k: v for k, v in mib_json.items() if k.startswith('myTable')}
            if table_info:
                myTable = self.MibTable(tuple(table_info['myTable']['oid']))
                myTableEntry = self.MibTableRow(tuple(table_info['myTableEntry']['oid'])).setIndexNames((0, f'__{mib}', 'myTableIndex'))
                myTableIndex = self.MibTableColumn(tuple(table_info['myTableIndex']['oid']), Integer())
                myTableName = self.MibTableColumn(tuple(table_info['myTableName']['oid']), OctetString())
                myTableValue = self.MibTableColumn(tuple(table_info['myTableValue']['oid']), Integer())
                myTableStatus = self.MibTableColumn(tuple(table_info['myTableStatus']['oid']), OctetString())
                self.mibBuilder.export_symbols(
                    f'__{mib}',
                    myTable=myTable,
                    myTableEntry=myTableEntry,
                    myTableIndex=myTableIndex,
                    myTableName=myTableName,
                    myTableValue=myTableValue,
                    myTableStatus=myTableStatus,
                )
                # Populate table with demo data (same as before)
                snmpContext = context.SnmpContext(self.snmpEngine)
                mibInstrumentation = snmpContext.get_mib_instrum()
                (myTableEntry, myTableIndex, myTableName,
                 myTableValue, myTableStatus) = self.mibBuilder.importSymbols(
                    f'__{mib}', 'myTableEntry', 'myTableIndex', 'myTableName',
                    'myTableValue', 'myTableStatus'
                )
                for row in self.table_rows:
                    idx, name, value, status = row
                    rowInstanceId = myTableEntry.getInstIdFromIndices(idx)
                    mibInstrumentation.write_variables(
                        (myTableIndex.name + rowInstanceId, idx),
                        (myTableName.name + rowInstanceId, name),
                        (myTableValue.name + rowInstanceId, value),
                        (myTableStatus.name + rowInstanceId, status),
                    )

    def run(self) -> None:
        """Run the SNMP agent (blocking)."""
        print(f'SNMP agent running on {self.host}:{self.port}')
        print(f'Community: public')
        print(f'Enterprise OID: .1.3.6.1.4.1.99999')
        print(f'Try: snmpwalk -v2c -c public {self.host}:{self.port} .1.3.6.1.4.1.99999')
        print('Press Ctrl+C to stop')

        self.snmpEngine.transport_dispatcher.job_started(1)
        try:
            # For pysnmp v7 with asyncio, we need to create/get event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_forever()
        except KeyboardInterrupt:
            print('\nShutting down agent')
        finally:
            self.snmpEngine.transport_dispatcher.close_dispatcher()

    def stop(self) -> None:
        """Stop the SNMP agent."""
        self.snmpEngine.transport_dispatcher.close_dispatcher()

    async def send_trap_async(self, trap_dest: Tuple[str, int], oid: Tuple[int, ...],
                              value: Any, trap_type: str = 'trap') -> None:
        """Send an SNMP trap or inform notification.

        Args:
            trap_dest: Tuple of (host, port) for trap destination
            oid: OID tuple for the trap variable binding
            value: Value to send with the trap
            trap_type: 'trap' or 'inform'
        """
        logger = logging.getLogger(__name__)
        try:
            # Create a notification type with the OID and value
            result = await send_notification(
                SnmpEngine(),
                CommunityData('public'),
                await UdpTransportTarget.create(trap_dest),
                ContextData(),
                trap_type,
                NotificationType(ObjectIdentity(1, 3, 6, 1, 6, 3, 1, 1, 5, 1)).add_var_binds((oid, value))
            )

            errorIndication = result[0]
            if errorIndication:
                logger.error(f'Trap send error: {errorIndication}')
            else:
                logger.info(f'Trap sent to {trap_dest} for OID {oid} with value {value}')
        except Exception as e:
            logger.error(f'Exception sending trap: {e}')

    def send_trap(self, trap_dest: Tuple[str, int], oid: Tuple[int, ...],
                  value: Any, trap_type: str = 'trap') -> None:
        """Send an SNMP trap synchronously (wrapper for async method).

        Args:
            trap_dest: Tuple of (host, port) for trap destination
            oid: OID tuple for the trap variable binding
            value: Value to send with the trap
            trap_type: 'trap' or 'inform'
        """
        asyncio.run(self.send_trap_async(trap_dest, oid, value, trap_type))


def main() -> None:
    """Main entry point."""
    agent = SNMPAgent()
    agent.run()


if __name__ == "__main__":
    main()
