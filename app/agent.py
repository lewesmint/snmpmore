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
from typing import Any, Tuple, List, cast, Optional
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

        # Import special TextualConventions from SNMPv2-TC for proper handling
        (self.RowStatus,) = self.mibBuilder.import_symbols('SNMPv2-TC', 'RowStatus')
        (self.TestAndIncr,) = self.mibBuilder.import_symbols('SNMPv2-TC', 'TestAndIncr')

        # Counter for dynamic scalar
        self.counter = 0
        self.counter_lock = threading.Lock()

        # Start time for TimeTicks
        self.start_time = time.time()

        # Create a dynamic uptime MibScalarInstance subclass
        agent_ref = self
        MibScalarInstanceBase = self.MibScalarInstance

        class DynamicUptimeInstance(MibScalarInstanceBase):  # type: ignore[valid-type,misc]
            """MibScalarInstance that returns current uptime on each GET."""
            def getValue(self, name: Any, **context: Any) -> Any:
                uptime_ticks = int((time.time() - agent_ref.start_time) * 100)
                return TimeTicks(uptime_ticks)

        self.DynamicUptimeInstance = DynamicUptimeInstance

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
                                m = re.search(r'mibBuilder\.exportSymbols\(["\']([A-Za-z0-9\-_.]+)["\']', line)
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
        """Load config YAML, ensure compiled MIBs and JSONs exist, generate if missing, using runtime classes.
        Build and generate in dependency order."""
        import re
        from collections import defaultdict, deque
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found")
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        mibs: List[str] = config_data.get('mibs', [])
        mib_compiler = MibCompiler()
        behaviour_gen = BehaviourGenerator()
        compiled_dir = 'compiled-mibs'
        # Gather all subdirs (including base)
        mib_root = 'data/mibs'
        search_paths = [root for root, _, _ in os.walk(mib_root)] if os.path.exists(mib_root) else []
        system_mib_dir = r'c:\net-snmp\share\snmp\mibs'
        if os.path.exists(system_mib_dir):
            search_paths.append(system_mib_dir)

        # Find all MIB source files
        mib_files = []
        for d in search_paths:
            if not os.path.exists(d):
                continue
            for root, _dirs, files in os.walk(d):
                for fname in files:
                    if fname.endswith(('.my', '.txt', '.mib')):
                        mib_files.append(os.path.join(root, fname))

        # Map: mib_name -> (src_path, set(imported_mibs))
        mib_imports = {}
        mib_name_to_file = {}
        for path in mib_files:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            # Find MIB name
            mib_name = None
            for line in lines:
                m = re.match(r'\s*([A-Za-z0-9\-_.]+)\s+DEFINITIONS\s+::=\s+BEGIN', line)
                if m:
                    mib_name = m.group(1)
                    break
            if not mib_name:
                continue
            mib_name_to_file[mib_name] = path
            # Find IMPORTS section
            imported = set()
            in_imports = False
            for line in lines:
                l = line.strip()
                if l.startswith('IMPORTS'):
                    in_imports = True
                    continue
                if in_imports:
                    if ';' in l:
                        in_imports = False
                        l = l.split(';')[0]
                    parts = l.split('FROM')
                    if len(parts) == 2:
                        dep = parts[1].strip().rstrip(';').split()[0]
                        imported.add(dep)
            mib_imports[mib_name] = (path, imported)

        # Build dependency graph
        edges = defaultdict(set)
        reverse_edges = defaultdict(set)
        for mib, (_path, imports) in mib_imports.items():
            for dep in imports:
                if dep in mib_imports:
                    edges[mib].add(dep)
                    reverse_edges[dep].add(mib)

        # Topological sort
        order = []
        no_deps = deque([mib for mib in mib_imports if not edges[mib]])
        visited = set()
        while no_deps:
            mib = no_deps.popleft()
            if mib in visited:
                continue
            order.append(mib)
            visited.add(mib)
            for child in reverse_edges[mib]:
                edges[child].remove(mib)
                if not edges[child]:
                    no_deps.append(child)
        # Add any remaining (cyclic or missing) at the end
        for mib in mib_imports:
            if mib not in visited:
                order.append(mib)

        # Only build MIBs that are in the config or are dependencies of those
        required = set()
        def collect_deps(mib: str) -> None:
            if mib in required:
                return
            required.add(mib)
            for dep in mib_imports.get(mib, (None, set()))[1]:
                collect_deps(dep)
        for mib in mibs:
            collect_deps(mib)
        build_order = [mib for mib in order if mib in required]

        # Track which MIBs were compiled in this session
        compiled_this_session = set()

        for mib in build_order:
            src_path = mib_name_to_file.get(mib)
            if not src_path:
                print(f"WARNING: No source file found for {mib}, skipping.")
                continue
            compiled_py = os.path.join(compiled_dir, f'{mib}.py')
            json_path = os.path.join('mock-behaviour', f'{mib}_behaviour.json')

            # Compile if needed
            if not os.path.exists(compiled_py):
                try:
                    compiled_py = mib_compiler.compile(src_path)
                    # Check if this specific MIB was compiled (not just dependencies)
                    if mib in mib_compiler.last_compile_results:
                        status = mib_compiler.last_compile_results[mib]
                        if status == 'compiled':
                            compiled_this_session.add(mib)
                            print(f"{mib}: compiled")
                except Exception as e:
                    print(f"FATAL: Failed to compile {mib}: {e}")
                    import sys
                    sys.exit(1)

            # Generate behaviour JSON if needed
            if not os.path.exists(json_path):
                try:
                    json_path = behaviour_gen.generate(compiled_py, mib)
                    # Note: generate() already prints "Behaviour JSON written to" message
                except Exception as e:
                    print(f"FATAL: Failed to generate behaviour JSON for {mib}: {e}")
                    import sys
                    sys.exit(1)

            # Only load JSONs for MIBs in config
            if mib in mibs:
                with open(json_path, 'r') as jf:
                    self.mib_jsons[mib] = json.load(jf)
                print(f"{mib}: loaded from behaviour JSON")

    def _setup_transport(self) -> None:
        """Configure UDP transport."""
        config.add_transport(
            self.snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode((self.host, self.port))
        )

    def _setup_community(self) -> None:
        """Configure SNMPv2c community with explicit VACM setup, restricting snmpModules (.1.3.6.1.6.3)."""
        # Add community
        config.add_v1_system(self.snmpEngine, 'my-area', 'public')

        # Setup VACM context
        config.add_context(self.snmpEngine, '')

        # Setup VACM group
        config.add_vacm_group(self.snmpEngine, 'mygroup', 2, 'my-area')

        # Setup restricted view: include .1.3.6.1, exclude .1.3.6.1.6.3
        config.add_vacm_view(self.snmpEngine, 'restrictedView', 1, (1, 3, 6, 1), '')  # included
        config.add_vacm_view(self.snmpEngine, 'restrictedView', 2, (1, 3, 6, 1, 6, 3), '')  # excluded

        # Setup VACM access for the group, using the restricted view for read/write/notify
        config.add_vacm_access(
            self.snmpEngine,
            'mygroup',  # groupName
            '',         # contextPrefix
            2,          # securityModel (v2c)
            'noAuthNoPriv',  # securityLevel
            'exact',    # contextMatch
            'restrictedView',  # readView
            'restrictedView',  # writeView
            'restrictedView'   # notifyView
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
            # Custom types - map to base SNMP types
            'InterfaceIndex': Integer32,
            'InterfaceIndexOrZero': Integer32,
            'EntPhysicalIndexOrZero': Integer32,
            'CoiAlarmObjectTypeClass': Integer32,
            'InetAddressType': Integer32,
            'InetAddress': OctetString,
            'InetPortNumber': Unsigned32,
            'TruthValue': Integer32,
            'TimeStamp': TimeTicks,
            'TestAndIncr': self.TestAndIncr,  # Use actual TestAndIncr from SNMPv2-TC
            'AutonomousType': ObjectIdentifier,
            'RowStatus': self.RowStatus,  # Use actual RowStatus from SNMPv2-TC
            'PhysAddress': OctetString,
            'OwnerString': OctetString,
            'DateAndTime': OctetString,
            # HOST-RESOURCES-MIB custom types
            'ProductID': ObjectIdentifier,  # TextualConvention based on ObjectIdentifier
            'InternationalDisplayString': OctetString,  # TextualConvention based on OctetString
            'KBytes': Integer32,  # TextualConvention based on Integer32
            # IANAifType-MIB custom types
            'IANAifType': Integer32,  # TextualConvention based on Integer32 (enum for interface types)
        }

        for mib, mib_json in self.mib_jsons.items():
            table_related_objects = self._find_table_related_objects(mib_json)
            self._register_scalars(mib, mib_json, table_related_objects, type_map)
            self._register_tables(mib, mib_json, type_map)

    def _find_table_related_objects(self, mib_json: dict[str, Any]) -> set[str]:
        """Return set of table-related object names (tables, entries, columns)."""
        table_related_objects = set()
        for name, info in mib_json.items():
            if name.endswith('Table') or name.endswith('Entry'):
                table_related_objects.add(name)
                if name.endswith('Entry'):
                    entry_oid = tuple(info.get('oid', []))
                    for col_name, col_info in mib_json.items():
                        col_oid = tuple(col_info.get('oid', []))
                        if (len(col_oid) == len(entry_oid) + 1 and col_oid[:len(entry_oid)] == entry_oid):
                            table_related_objects.add(col_name)
        return table_related_objects

    def _get_pysnmp_type_from_info(self, type_name: str, type_info: Optional[dict[str, Any]], type_map: dict[str, Any]) -> Any:
        """Get the pysnmp type class from type_info or type_map."""
        # If we have type_info with base_type, use that
        if type_info and 'base_type' in type_info:
            base_type_name = type_info['base_type']
            if base_type_name in type_map:
                return type_map[base_type_name]

        # Fall back to type_map lookup
        if type_name in type_map:
            return type_map[type_name]

        # Default fallback
        return OctetString

    def _get_snmp_value(self, pysnmp_type: type, initial_value: Any, type_name: str = '', symbol_name: str = '', type_info: Optional[dict[str, Any]] = None) -> Any:
        """Return a pysnmp value for a given type and initial value, with sensible defaults."""
        # Use type_info if available to determine base type
        if type_info:
            base_type = type_info.get('base_type', type_name)
        else:
            base_type = type_name

        # Handle special types that need specific default values
        if initial_value is None or initial_value == 0 or initial_value == '':
            # TruthValue: 1=true, 2=false (never 0)
            if type_name == 'TruthValue':
                return Integer32(2)  # Default to false
            # DateAndTime: 8 or 11 byte OctetString with specific format
            # Format: year(2 bytes), month, day, hour, min, sec, decisec, [direction, offset_hour, offset_min]
            if type_name == 'DateAndTime':
                # Check if initial_value is already a hex string
                if isinstance(initial_value, str) and len(initial_value) == 16:
                    # Assume it's a hex string like '07D0010100000000'
                    return OctetString(hexValue=initial_value)
                # Default to 2000-01-01 00:00:00.0 (8 bytes)
                # year=2000 (0x07D0), month=1, day=1, hour=0, min=0, sec=0, decisec=0
                return OctetString(hexValue='07D0010100000000')
            # OwnerString: DisplayString but may have specific constraints
            if type_name == 'OwnerString':
                return OctetString('admin')
            # TestAndIncr: Use actual TestAndIncr type from SNMPv2-TC
            if type_name == 'TestAndIncr':
                return self.TestAndIncr(0)
            # RowStatus: Use notInService(2) as safe default for read-only contexts
            if type_name == 'RowStatus':
                return self.RowStatus(2)  # notInService

        if initial_value is not None and initial_value != '':
            # Handle TestAndIncr specially - use the actual TestAndIncr class
            if type_name == 'TestAndIncr':
                return self.TestAndIncr(int(initial_value))
            # Handle RowStatus specially - use the actual RowStatus class
            if type_name == 'RowStatus':
                return self.RowStatus(int(initial_value))
            if pysnmp_type in (Integer32, Integer, Counter32, Counter64, Gauge32, Unsigned32, TimeTicks):
                # Handle empty string for integer types
                if isinstance(initial_value, str) and initial_value.strip() == '':
                    return pysnmp_type(0)
                return pysnmp_type(initial_value)
            if pysnmp_type is OctetString:
                # Check if this is a DateAndTime hex value
                if type_name == 'DateAndTime' and isinstance(initial_value, str) and len(initial_value) == 16:
                    return OctetString(hexValue=initial_value)
                return OctetString(str(initial_value))
            if pysnmp_type is IpAddress:
                return IpAddress(str(initial_value) or '0.0.0.0')
            if pysnmp_type is ObjectIdentifier:
                # Handle ObjectIdentifier - convert string like "0.0" to tuple
                if isinstance(initial_value, str):
                    return ObjectIdentifier(initial_value)
                return pysnmp_type(initial_value)
            return pysnmp_type(initial_value)
        # Defaults
        default_map = {
            OctetString: OctetString(''),
            IpAddress: IpAddress('0.0.0.0'),
            TimeTicks: TimeTicks(0),
            ObjectIdentifier: ObjectIdentifier('0.0'),  # Default OID for null values
        }
        if pysnmp_type in (Integer32, Integer, Counter32, Counter64, Gauge32, Unsigned32):
            return pysnmp_type(0)
        return default_map.get(pysnmp_type, pysnmp_type())

    def _register_scalars(self, mib: str, mib_json: dict[str, Any], table_related_objects: set[str], type_map: dict[str, Any]) -> None:
        """Register scalar objects for a MIB, skipping table-related objects."""
        scalar_symbols: list[Any] = []
        registered_count = 0
        for name, info in mib_json.items():
            if name in table_related_objects:
                continue
            oid_value = cast(List[int], info['oid']) if isinstance(info['oid'], list) else []
            type_info = info.get('type_info')
            # Use type_info to get the correct pysnmp type, or fall back to type_map
            pysnmp_type = self._get_pysnmp_type_from_info(info['type'], type_info, type_map)
            if (isinstance(info['oid'], list) and
                len(oid_value) > 0 and
                info.get('access') not in ['not-accessible', 'accessible-for-notify']):
                scalar_oid = tuple(oid_value)
                dynamic_func = info.get('dynamic_function')
                scalar_symbols.append(self.MibScalar(scalar_oid, pysnmp_type()))

                if dynamic_func == 'uptime':
                    # Use dynamic instance that computes uptime on each GET
                    scalar_symbols.append(self.DynamicUptimeInstance(scalar_oid, (0,), TimeTicks(0)))
                else:
                    value_str = info.get('current') if 'current' in info else info.get('initial')
                    value = self._get_snmp_value(pysnmp_type, value_str, info['type'], name, type_info)
                    scalar_symbols.append(self.MibScalarInstance(scalar_oid, (0,), value))
                registered_count += 1
        if scalar_symbols:
            export_name = mib if mib.startswith('SNMPv2-') else f'__{mib}'
            self.mibBuilder.export_symbols(export_name, *scalar_symbols)
            print(f"Loaded {mib}: {registered_count} objects")

    def _register_tables(self, mib: str, mib_json: dict[str, Any], type_map: dict[str, Any]) -> None:
        """Detect and register all tables in the MIB with a single row instance."""
        # Skip table registration for standard SNMPv2 and UDP MIBs - they have complex indexes
        if mib.startswith('SNMPv2-') or mib == 'UDP-MIB':
            return

        # Find all tables by looking for objects ending in "Table"
        tables: dict[str, dict[str, Any]] = {}

        for name, info in mib_json.items():
            if name.endswith('Table') and info.get('access') == 'not-accessible':
                # Found a table, now find its entry and columns
                table_prefix = name[:-5]  # Remove "Table" suffix
                entry_name = f"{table_prefix}Entry"

                # Check if entry exists
                if entry_name not in mib_json:
                    continue

                entry_oid = tuple(mib_json[entry_name]['oid'])

                # Collect all columns for this table by checking OID hierarchy
                # Columns must be direct children of the entry OID
                columns = {}
                for col_name, col_info in mib_json.items():
                    if col_name in [name, entry_name]:
                        continue
                    col_oid = tuple(col_info.get('oid', []))
                    # Check if column OID is a child of entry OID
                    # e.g., entry: (1,3,6,1,2,1,7,5,1), column: (1,3,6,1,2,1,7,5,1,1)
                    if (len(col_oid) == len(entry_oid) + 1 and
                        col_oid[:len(entry_oid)] == entry_oid):
                        columns[col_name] = col_info

                if columns:
                    tables[name] = {
                        'table': info,
                        'entry': mib_json[entry_name],
                        'columns': columns,
                        'prefix': table_prefix
                    }

        # Register each table
        for table_name, table_data in tables.items():
            try:
                self._register_single_table(mib, table_name, table_data, type_map)
            except Exception as e:
                print(f"Warning: Could not register table {table_name}: {e}")

    def _register_single_table(self, mib: str, table_name: str, table_data: dict[str, Any], type_map: dict[str, Any]) -> None:
        """Register a single table with one row instance."""
        table_oid = tuple(table_data['table']['oid'])
        entry_oid = tuple(table_data['entry']['oid'])
        columns = table_data['columns']
        prefix = table_data['prefix']

        export_name = mib if mib.startswith('SNMPv2-') else f'__{mib}'

        # Check if table is already registered
        try:
            existing = self.mibBuilder.import_symbols(export_name, table_name)
            if existing:
                raise Exception(f"Symbol {table_name} already exported at {export_name}")
        except Exception as e:
            if "already exported" in str(e):
                raise
            # Symbol doesn't exist, which is what we want
            pass

        # Create table and entry objects
        table_obj = self.MibTable(table_oid)

        # Find the index column (usually the first column or one with "Index" in name)
        # For AUGMENTS tables (like ifXTable), they inherit the index from the base table
        index_col_name = None
        index_is_inherited = False
        entry_info = table_data['entry']

        # Check if this is an AUGMENTS table (detected by generator)
        # The generator marks tables with 'index_from' when their index columns are inherited
        if 'index_from' in entry_info and entry_info['index_from']:
            index_is_inherited = True

            # Check for additional local index columns (not-accessible columns)
            # Tables like ifRcvAddressTable have both inherited index AND local index columns
            # These multi-column indexes are complex - skip them for now
            local_index_cols = [c for c, i in columns.items() if i.get('access') == 'not-accessible']
            if local_index_cols:
                print(f"Warning: Skipping table {table_name}: has complex multi-column index (inherited + local)")
                return

            # For inherited index tables, prefer an Integer32-typed column for setIndexNames
            # to avoid type mismatch issues (pysnmp uses the column type for index encoding)
            # The actual index is simple integer (1,) so we need an integer-compatible column
            for col_name, col_info in columns.items():
                col_base_type = col_info.get('type_info', {}).get('base_type', col_info['type'])
                if col_base_type in ('Integer32', 'Integer', 'Counter32', 'Gauge32', 'Unsigned32'):
                    index_col_name = col_name
                    break
            # Fallback to first column if no integer column found
            if not index_col_name:
                index_col_name = list(columns.keys())[0]
        else:
            # Non-inherited tables: look for index column by name or access
            for col_name, col_info in columns.items():
                if 'Index' in col_name or col_info.get('access') == 'not-accessible':
                    index_col_name = col_name
                    break
            if not index_col_name:
                index_col_name = list(columns.keys())[0]

        # Always instantiate at least one row for every table, using correct index type
        try:
            entry_obj = self.MibTableRow(entry_oid).setIndexNames((0, export_name, index_col_name))
        except Exception as e:
            print(f"Warning: Could not register table {table_name}: could not create entry object: {e}")
            return

        # Create column objects
        column_objects = {}
        symbols_to_export = {
            table_name: table_obj,
            f"{prefix}Entry": entry_obj
        }

        for col_name, col_info in columns.items():
            col_oid = tuple(col_info['oid'])
            col_type_name = col_info['type']
            pysnmp_type = type_map.get(col_type_name, Integer32)

            # Try to import the actual type from compiled MIBs (for TextualConventions like PhysAddress)
            # This preserves attributes like fixed_length that pysnmp may need
            type_instance = None
            try:
                # Try importing from SNMPv2-TC first (common textual conventions)
                imported_type = self.mibBuilder.import_symbols('SNMPv2-TC', col_type_name)
                if imported_type and len(imported_type) > 0:
                    type_instance = imported_type[0]()
            except Exception:
                pass

            # If not found, use the mapped base type
            if type_instance is None:
                type_instance = pysnmp_type()

            col_obj = self.MibTableColumn(col_oid, type_instance)
            column_objects[col_name] = col_obj
            symbols_to_export[col_name] = col_obj

        # Export all table symbols
        self.mibBuilder.export_symbols(export_name, **symbols_to_export)

        # Create a single row instance
        # Determine the index type from the index column
        index_col_type = columns[index_col_name]['type']
        index_type_info = columns[index_col_name].get('type_info')
        index_pysnmp_type = self._get_pysnmp_type_from_info(index_col_type, index_type_info, type_map)

        # Determine the appropriate index value based on the type
        # For integer-like types, use 1; for string-like types, use a simple value
        # For inherited indexes (AUGMENTS tables), always use integer
        index_value: Any
        if index_is_inherited:
            # AUGMENTS tables inherit integer index from base table
            index_value = 1
        elif index_pysnmp_type in (Integer32, Integer, Unsigned32, Gauge32, Counter32, Counter64, TimeTicks):
            index_value = 1
        elif index_col_type == 'PhysAddress':
            # PhysAddress expects hex bytes (MAC address format)
            index_value = "00:11:22:33:44:55"
        elif index_pysnmp_type is OctetString:
            # For OctetString indexes, use a simple string value
            index_value = "eth0"
        elif index_pysnmp_type is IpAddress:
            index_value = "127.0.0.1"
        elif index_pysnmp_type is ObjectIdentifier:
            # For ObjectIdentifier indexes, use a simple OID
            index_value = "1.3.6.1.1"
        else:
            # Default to integer for unknown types
            index_value = 1

        snmpContext = context.SnmpContext(self.snmpEngine)
        mibInstrumentation = snmpContext.get_mib_instrum()
        try:
            entry_imported = self.mibBuilder.import_symbols(export_name, f"{prefix}Entry")[0]

            # For AUGMENTS tables, construct row instance ID directly as simple integer tuple
            # This avoids issues with getInstIdFromIndices() using wrong column type for encoding
            if index_is_inherited:
                rowInstanceId = (index_value,)  # Simple integer index tuple
            else:
                rowInstanceId = entry_imported.getInstIdFromIndices(index_value)

            # Populate columns with default values
            write_vars = []
            failed_columns = []
            for col_name, col_info in columns.items():
                col_imported = self.mibBuilder.import_symbols(export_name, col_name)[0]
                col_type_name = col_info['type']
                type_info = col_info.get('type_info')
                pysnmp_type = self._get_pysnmp_type_from_info(col_type_name, type_info, type_map)
                initial_value = col_info.get('initial')

                # For RowStatus, use createAndGo(4) to create a new active row
                # (RFC 2579: cannot set active(1) directly on new row)
                if col_type_name == 'RowStatus':
                    initial_value = 4  # createAndGo

                try:
                    value = self._get_snmp_value(pysnmp_type, initial_value, col_type_name, col_name, type_info)
                    write_vars.append((col_imported.name + rowInstanceId, value))
                except Exception as e:
                    failed_columns.append(f"{col_name} ({col_type_name})")
                    continue

            if write_vars:
                # Try batch write first (most efficient)
                try:
                    mibInstrumentation.write_variables(*write_vars)
                    print(f"Loaded {mib} table {table_name}: {len(columns)} columns, 1 row instance")
                except Exception as e:
                    # Batch write fails for tables with TestAndIncr columns (special locking semantics)
                    # Individual writes handle this correctly - see docs/SNMP_ROW_CREATION_AND_SET_SEMANTICS.md
                    col_names = list(columns.keys())
                    failed_columns = []
                    success_count = 0
                    for idx, (oid, value) in enumerate(write_vars):
                        col_name = col_names[idx] if idx < len(col_names) else f"column_{idx}"
                        col_type = columns[col_name]['type'] if col_name in columns else "unknown"
                        try:
                            mibInstrumentation.write_variables((oid, value))
                            success_count += 1
                        except Exception as col_error:
                            failed_columns.append(f"{col_name} ({col_type})")

                    if success_count == len(write_vars):
                        print(f"Loaded {mib} table {table_name}: {len(columns)} columns, 1 row instance (individual writes)")
                    elif failed_columns:
                        print(f"Warning: Could not register table {table_name}: Failed columns: {', '.join(failed_columns)}")
                    else:
                        raise e
        except Exception as e:
            print(f"Warning: Could not register table {table_name}: {e}")

    def run(self) -> None:
        """Run the SNMP agent (blocking)."""
        print(f'SNMP agent running on {self.host}:{self.port}')
        print(f'Community: public')
        print(f'Try: snmpwalk -v2c -c public localhost:{self.port}')
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
