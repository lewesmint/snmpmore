#!/usr/bin/env python3
"""
SNMP agent using pysnmp that exposes scalars and tables as defined in MY-AGENT-MIB.
Listens on UDP port 11161 (non-privileged) and responds to SNMP queries.
"""

import threading
import asyncio
import time
import logging
import os
import yaml
import json
from typing import Any, Tuple, List, cast
from app.compiler import MibCompiler
from app.generator import BehaviourGenerator
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
        """Set a scalar value and persist it to the behaviour JSON file."""
        # Find the MibScalarInstance for the given OID and set its value (as OctetString)
        mibInstrum = context.SnmpContext(self.snmpEngine).get_mib_instrum()
        mibInstrum.write_variables((oid, OctetString(value)))

        # Persist the change to the behaviour JSON file
        self._persist_scalar_value(oid, value)

    def _persist_scalar_value(self, oid: Tuple[int, ...], value: str) -> None:
        """Persist a scalar value change to the behaviour JSON file.

        Updates the 'current' field in the behaviour JSON, leaving 'initial' unchanged
        so values can be reset later.
        """
        # Strip the .0 instance identifier from scalar OIDs
        # e.g., (1,3,6,1,2,1,1,1,0) -> (1,3,6,1,2,1,1,1)
        base_oid = oid[:-1] if oid and oid[-1] == 0 else oid

        # Find which MIB this OID belongs to
        for mib_name, mib_json in self.mib_jsons.items():
            for symbol_name, info in mib_json.items():
                if isinstance(info['oid'], list) and tuple(info['oid']) == base_oid:
                    # Found the matching symbol, update the current value
                    info['current'] = value

                    # Write back to the JSON file
                    json_path = os.path.join('mock-behaviour', f'{mib_name}_behaviour.json')
                    with open(json_path, 'w') as f:
                        json.dump(mib_json, f, indent=2)

                    print(f"Persisted {symbol_name} = '{value}' to {json_path}")
                    return

        print(f"Warning: Could not find OID {oid} in any loaded MIB to persist")

    def __init__(self, host: str = '127.0.0.1', port: int = 161, config_path: str = 'agent_config.yaml') -> None:
        """Initialize the SNMP agent with config file support.

        Args:
            host: IP address to bind to
            port: UDP port to listen on (default 11161 for non-root)
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

    def _find_compiled_py_by_mib_name(self, mib_name: str, compiled_dir: str = 'compiled-mibs') -> str:
        """Scan compiled-mibs for .py files whose export symbol matches mib_name."""
        import re
        for fname in os.listdir(compiled_dir):
            if fname.endswith('.py'):
                fpath = os.path.join(compiled_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        for line in f:
                            if 'mibBuilder.exportSymbols' in line:
                                m = re.search(r'mibBuilder\.exportSymbols\(["\\']([A-Za-z0-9\-_.]+)["\\']', line)
                                if m and m.group(1) == mib_name:
                                    return fpath
                except Exception:
                    pass
        raise FileNotFoundError(f"Compiled MIB .py for {mib_name} not found in {compiled_dir}")

    def _find_mib_source_by_name(self, mib_name: str, search_paths: list[str]) -> str:
        """Scan all files in search_paths, parse for internal MIB name, and match to mib_name."""
        import re
        for search_path in search_paths:
            for root, _dirs, files in os.walk(search_path):
                for fname in files:
                    # Only consider likely MIB files
                    if not fname.lower().endswith(('.txt', '.mib', '')):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                # Look for 'UDP-MIB DEFINITIONS ::= BEGIN'
                                m = re.match(r'\s*([A-Za-z0-9\-_.]+)\s+DEFINITIONS\s+::=\s+BEGIN', line)
                                if m and m.group(1) == mib_name:
                                    return fpath
                    except Exception:
                        continue
        raise FileNotFoundError(f"MIB source for {mib_name} not found in search paths {search_paths}")

    def _load_config_and_prepare_mibs(self, config_path: str) -> None:
        """Load config YAML, ensure compiled MIBs and JSONs exist, generate if missing, using runtime classes."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found")
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        mibs: List[str] = config_data.get('mibs', [])
        mib_compiler = MibCompiler()
        behaviour_gen = BehaviourGenerator()
        for mib in mibs:
            json_path = os.path.join('mock-behaviour', f'{mib}_behaviour.json')
            if os.path.exists(json_path):
                with open(json_path, 'r') as jf:
                    self.mib_jsons[mib] = json.load(jf)
                print(f"{mib}: loaded from existing behaviour JSON")
            else:
                # Try to find compiled .py by export symbol
                try:
                    compiled_py = self._find_compiled_py_by_mib_name(mib)
                except FileNotFoundError:
                    # If not found, compile from any file with matching internal MIB name
                    search_paths = ['data/mibs']
                    system_mib_dir = r'c:\net-snmp\share\snmp\mibs'
                    if os.path.exists(system_mib_dir):
                        search_paths.append(system_mib_dir)
                    mib_txt = self._find_mib_source_by_name(mib, search_paths)
                    compiled_py = mib_compiler.compile(mib_txt)
                json_path = behaviour_gen.generate(compiled_py, mib)
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

        # Allow access to the standard SNMP system group subtree (1.3.6.1.2.1.1)
        config.add_vacm_user(
            self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
            (1, 3, 6, 1, 2, 1, 1)
        )
        # Allow access to entire MIB-2 tree (1.3.6.1.2.1) for standard MIBs
        config.add_vacm_user(
            self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
            (1, 3, 6, 1, 2, 1)
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
            'ObjectIdentifier': ObjectIdentifier,
        }

        # Register all MIBs from config (including SNMPv2-MIB system group)
        for mib, mib_json in self.mib_jsons.items():
            # Scalars
            scalar_symbols: list[Any] = []
            registered_count = 0
            for name, info in mib_json.items():
                oid_value = cast(List[int], info['oid']) if isinstance(info['oid'], list) else []
                # Register scalar objects (skip tables and non-accessible objects)
                if (info['type'] in type_map and
                    isinstance(info['oid'], list) and
                    len(oid_value) > 0 and
                    info.get('access') not in ['not-accessible', 'accessible-for-notify']):
                    pysnmp_type = type_map[info['type']]
                    scalar_oid = tuple(oid_value)

                    # Check if this is a dynamic function
                    dynamic_func = info.get('dynamic_function')
                    if dynamic_func == 'uptime':
                        # Special handling for sysUpTime - calculate from start_time
                        value = TimeTicks(int((time.time() - self.start_time) * 100))
                    else:
                        # Use 'current' if it exists, otherwise fall back to 'initial'
                        value_str = info.get('current') if 'current' in info else info.get('initial')
                        if value_str is not None:
                            value = pysnmp_type(value_str)
                        else:
                            # No initial/current value, use type-appropriate defaults
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
                    registered_count += 1
            if scalar_symbols:
                # Use actual MIB name for standard MIBs (SNMPv2-MIB, etc.)
                # Use __MIB for custom MIBs to avoid conflicts
                export_name = mib if mib.startswith('SNMPv2-') else f'__{mib}'
                self.mibBuilder.export_symbols(export_name, *scalar_symbols)
                print(f"Loaded {mib}: {registered_count} objects")

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

        # Register an imaginary never-ending job to keep I/O dispatcher running forever
        self.snmpEngine.transport_dispatcher.job_started(1)

        # Run I/O dispatcher which would receive queries and send responses
        try:
            self.snmpEngine.open_dispatcher()
        except KeyboardInterrupt:
            print('\nShutting down agent')
        finally:
            self.snmpEngine.close_dispatcher()

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
