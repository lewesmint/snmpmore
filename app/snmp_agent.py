"""
SNMPAgent: Main orchestrator for the SNMP agent (initial workflow).
"""
from typing import cast
from app.app_logger import AppLogger
from app.app_config import AppConfig
from app.compiler import MibCompiler
import subprocess
import os
from pathlib import Path
import json
import time
from typing import Any, Dict, Optional
from pysnmp import debug as pysnmp_debug

class SNMPAgent:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11161,
        config_path: str = "agent_config.yaml",
    ) -> None:
        # Set up logging and config
        if not AppLogger._configured:
            self.app_config = AppConfig(config_path)
            AppLogger.configure(self.app_config)
        else:
            self.app_config = AppConfig(config_path)
        self.logger = AppLogger.get(__name__)
        pysnmp_debug.Debug("all")
        self.logger.info("PySNMP debugging enabled")

        self.config_path = config_path
        self.host = host
        self.port = port
        self.snmpEngine: Optional[Any] = None
        # self.mib_builder: Optional[Any] = None
        self.mib_jsons: Dict[str, Dict[str, Any]] = {}
        # Track agent start time for sysUpTime
        self.start_time = time.time()

    def run(self) -> None:
        self.logger.info("Starting SNMP Agent setup workflow...")
        # Compile MIBs and generate behavior JSONs as before
        mibs = cast(list[str], self.app_config.get("mibs", []))
        compiled_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "compiled-mibs")
        )
        json_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "mock-behaviour")
        )
        os.makedirs(json_dir, exist_ok=True)
        compiler = MibCompiler(compiled_dir, self.app_config)
        compiled_mib_paths: list[str] = []
        for mib_path in mibs:
            self.logger.info(f"Compiling MIB: {mib_path}")
            try:
                py_path = compiler.compile(mib_path)
                compiled_mib_paths.append(py_path)
                self.logger.info(f"Compiled {mib_path} to {py_path}")
            except Exception as e:
                self.logger.error(f"Failed to compile {mib_path}: {e}", exc_info=True)
                continue

        # Build and export the canonical type registry
        from app.type_registry import TypeRegistry

        type_registry = TypeRegistry(Path(compiled_dir))
        type_registry.build()
        type_registry.export_to_json("data/types.json")
        self.logger.info(
            f"Exported type registry to data/types.json with {len(type_registry.registry)} types."
        )

        # Validate types
        self.logger.info("Validating type registry...")
        try:
            subprocess.run(
                ["python3", "tools/validate_types.py", "data/types.json"], check=True
            )
            self.logger.info("Type registry validation passed.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Type registry validation failed: {e}")
            return

        # Generate JSON for MIB behavior
        from app.generator import BehaviourGenerator

        generator = BehaviourGenerator(json_dir)
        for py_path in compiled_mib_paths:
            self.logger.info(f"Generating behavior JSON for: {py_path}")
            try:
                generator.generate(py_path)
                self.logger.info(f"Behavior JSON generated for {py_path}")
            except Exception as e:
                self.logger.error(f"Failed to generate behavior JSON for {py_path}: {e}", exc_info=True)

        # Load behavior JSONs for SNMP serving
        for mib in mibs:
            json_path = os.path.join(json_dir, f"{mib}_behaviour.json")
            if os.path.exists(json_path):
                with open(json_path, "r") as jf:
                    self.mib_jsons[mib] = json.load(jf)
        self.logger.info("Loaded behavior JSONs for SNMP serving.")

        # Setup SNMP engine and transport
        self._setup_snmpEngine(compiled_dir)
        if self.snmpEngine is not None:
            self._setup_transport()
            self._setup_community()
            self._setup_responders()
            self._register_mib_objects()
            self.logger.info("SNMP Agent is now listening for SNMP requests.")
            # Block and serve SNMP requests using asyncio carrier correctly
            try:
                self.logger.info("Entering SNMP event loop...")
                self.snmpEngine.transport_dispatcher.job_started(1)

                # IMPORTANT: asyncio carrier uses open_dispatcher(), not run_dispatcher()
                self.snmpEngine.open_dispatcher()
            except KeyboardInterrupt:
                self.logger.info("Shutting down agent")
            except Exception as e:
                self.logger.error(f"SNMP event loop error: {e}", exc_info=True)
            finally:
                # Close dispatcher on exit
                self.snmpEngine.close_dispatcher()
        else:
            self.logger.error("snmpEngine is not initialized. SNMP agent will not start.")

    def _setup_snmpEngine(self, compiled_dir: str) -> None:
        from pysnmp.entity import engine
        from pysnmp.smi import builder

        self.logger.info("Setting up SNMP engine...")
        self.snmpEngine = engine.SnmpEngine()
        self.mib_builder = self.snmpEngine.get_mib_builder()

        # Add MIB sources
        self.mib_builder.add_mib_sources(builder.DirMibSource(compiled_dir))

        # Import MIB classes from SNMPv2-SMI
        (self.MibScalar,
         self.MibScalarInstance,
         self.MibTable,
         self.MibTableRow,
         self.MibTableColumn) = self.mib_builder.import_symbols(
            'SNMPv2-SMI',
            'MibScalar',
            'MibScalarInstance',
            'MibTable',
            'MibTableRow',
            'MibTableColumn'
        )

        self.logger.info("SNMP engine and MIB classes initialized")

    def _setup_transport(self) -> None:
        try:
            from pysnmp.carrier.asyncio.dgram import udp
            from pysnmp.entity import config
        except ImportError:
            raise RuntimeError("pysnmp is not installed or not available.")
        if self.snmpEngine is None:
            raise RuntimeError("snmpEngine is not initialized.")
        config.add_transport(
            self.snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode((self.host, self.port)),
        )

    def _setup_community(self) -> None:
        from pysnmp.entity import config

        if self.snmpEngine is None:
            raise RuntimeError("snmpEngine is not initialized.")
        config.add_v1_system(self.snmpEngine, "my-area", "public")
        config.add_context(self.snmpEngine, "")
        config.add_vacm_group(self.snmpEngine, "mygroup", 2, "my-area")
        config.add_vacm_view(self.snmpEngine, "restrictedView", 1, (1, 3, 6, 1), "")
        config.add_vacm_view(
            self.snmpEngine, "restrictedView", 2, (1, 3, 6, 1, 6, 3), ""
        )
        config.add_vacm_access(
            self.snmpEngine,
            "mygroup",
            "",
            2,
            "noAuthNoPriv",
            "exact",
            "restrictedView",
            "restrictedView",
            "restrictedView",
        )

    def _setup_responders(self) -> None:
        from pysnmp.entity.rfc3413 import cmdrsp, context

        if self.snmpEngine is None:
            raise RuntimeError("snmpEngine is not initialized.")
        snmpContext = context.SnmpContext(self.snmpEngine)
        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.SetCommandResponder(self.snmpEngine, snmpContext)

    def _register_mib_objects(self) -> None:
        # Register scalars and tables from behavior JSONs using the type registry
        if self.mib_builder is None:
            self.logger.error("mibBuilder is not initialized.")
            return

        # Load the type registry from the exported JSON file
        type_registry_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "types.json"
        )
        try:
            with open(type_registry_path, "r") as f:
                type_registry = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load type registry: {e}", exc_info=True)
            type_registry = {}

        # MibScalar, MibScalarInstance, MibTable, MibTableRow, MibTableColumn
        # are already imported as instance attributes in _setup_snmp_engine

        for mib, mib_json in self.mib_jsons.items():
            # Find table-related objects to skip them during scalar registration
            table_related_objects = self._find_table_related_objects(mib_json)

            # Register scalars (excluding table-related objects)
            self._register_scalars(mib, mib_json, table_related_objects, type_registry)

            # Register tables
            self._register_tables(mib, mib_json, type_registry)

    def _find_table_related_objects(self, mib_json: Dict[str, Any]) -> set[str]:
        """Return set of table-related object names (tables, entries, columns)."""
        table_related_objects: set[str] = set()
        for name, info in mib_json.items():
            if not isinstance(info, dict):
                continue
            if name.endswith('Table') or name.endswith('Entry'):
                table_related_objects.add(name)
                if name.endswith('Entry'):
                    entry_oid = tuple(info.get('oid', []))
                    # Find all columns that are children of this entry
                    for col_name, col_info in mib_json.items():
                        if not isinstance(col_info, dict):
                            continue
                        col_oid = tuple(col_info.get('oid', []))
                        if (len(col_oid) == len(entry_oid) + 1 and
                            col_oid[:len(entry_oid)] == entry_oid):
                            table_related_objects.add(col_name)
        return table_related_objects

    def _register_scalars(
        self,
        mib: str,
        mib_json: Dict[str, Any],
        table_related_objects: set[str],
        type_registry: Dict[str, Any]
    ) -> None:
        """Register scalar objects for a MIB, skipping table-related objects."""
        scalar_symbols = []
        for name, info in mib_json.items():
            if not isinstance(info, dict):
                continue

            # Skip table-related objects
            if name in table_related_objects:
                continue

            access = info.get("access")
            if access in ["not-accessible", "accessible-for-notify"]:
                continue
            oid = info.get("oid")
            oid_value = tuple(oid) if isinstance(oid, list) else ()
            value = info.get("current") if "current" in info else info.get("initial")
            type_name = info.get("type")
            type_info = type_registry.get(type_name, {}) if type_name else {}
            base_type = type_info.get("base_type") or type_name

            # Skip if we don't have a valid type name
            if not base_type or not isinstance(base_type, str):
                self.logger.warning(f"Skipping {name}: invalid type '{type_name}'")
                continue

            # Special handling for sysUpTime - use actual system uptime
            if name == "sysUpTime":
                # Calculate uptime in hundredths of a second (TimeTicks format)
                uptime_seconds = time.time() - self.start_time
                value = int(uptime_seconds * 100)
                self.logger.debug(
                    f"Setting sysUpTime to {value} (uptime: {uptime_seconds:.2f}s)"
                )

            # Handle None values with sensible defaults based on type
            if value is None:
                if base_type in [
                    "Integer32",
                    "Integer",
                    "Gauge32",
                    "Counter32",
                    "Counter64",
                    "TimeTicks",
                    "Unsigned32",
                ]:
                    value = 0
                elif base_type in ["OctetString", "DisplayString"]:
                    value = ""
                elif base_type == "ObjectIdentifier":
                    value = "0.0"
                else:
                    # Skip objects we can't provide a default for
                    self.logger.warning(
                        f"Skipping {name}: no value and no default for type '{base_type}'"
                    )
                    continue

            mib_scalar = None
            mib_scalar_instance = None
            # Try to resolve the SNMP type class dynamically
            pysnmp_type = None
            try:
                # Try to import the base type from SNMPv2-SMI or SNMPv2-TC
                try:
                    pysnmp_type = self.mib_builder.import_symbols(
                        "SNMPv2-SMI", base_type
                    )[0]
                except Exception:
                    try:
                        pysnmp_type = self.mib_builder.import_symbols(
                            "SNMPv2-TC", base_type
                        )[0]
                    except Exception:
                        # Fallback to pysnmp.proto.rfc1902 (correct module for base types)
                        from pysnmp.proto import rfc1902

                        pysnmp_type = getattr(rfc1902, base_type, None)
                if pysnmp_type is None:
                    raise ImportError(
                        f"Could not resolve SNMP type for base_type '{base_type}' (symbol {name})"
                    )
                # Use the MibScalar and MibScalarInstance classes we imported in _setup_snmp_engine
                mib_scalar = self.MibScalar(oid_value, pysnmp_type(value))
                mib_scalar_instance = self.MibScalarInstance(
                    oid_value, (0,), pysnmp_type(value)
                )
                self.logger.info(
                    f"Successfully registered {name} (type {type_name}, base {base_type})"
                )
            except Exception as e:
                self.logger.error(
                    f"Error registering {name} (type {type_name}, base {base_type}): {e}",
                    exc_info=True
                )
            if mib_scalar:
                scalar_symbols.append(mib_scalar)
            if mib_scalar_instance:
                scalar_symbols.append(mib_scalar_instance)
            if not type_info:
                self.logger.warning(
                    f"Type '{type_name}' for symbol '{name}' not found in type registry; used fallback."
                )
        if scalar_symbols:
            try:
                self.mib_builder.export_symbols(mib, *scalar_symbols)
                self.logger.info(f"Registered {len(scalar_symbols)} objects for {mib}")
            except Exception as e:
                self.logger.error(f"Error exporting symbols for {mib}: {e}", exc_info=True)

    def _register_tables(
        self,
        mib: str,
        mib_json: Dict[str, Any],
        type_registry: Dict[str, Any]
    ) -> None:
        """Detect and register all tables in the MIB, creating one row instance for each."""
        if self.MibTable is None or self.MibTableRow is None or self.MibTableColumn is None:
            self.logger.warning(f"Skipping table registration for {mib}: MIB table classes not available")
            return

        # Find all tables by looking for objects ending in "Table"
        tables: Dict[str, Dict[str, Any]] = {}

        for name, info in mib_json.items():
            if not isinstance(info, dict):
                continue
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
                    if not isinstance(col_info, dict):
                        continue
                    if col_name in [name, entry_name]:
                        continue
                    col_oid = tuple(col_info.get('oid', []))
                    # Check if column OID is a child of entry OID
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
            self.logger.debug(f"Processing table: {table_name} (entry: {table_data['entry']})")
            try:
                self._register_single_table(mib, table_name, table_data, type_registry)
            except Exception as e:
                self.logger.warning(f"Could not register table {table_name}: {e}", exc_info=True)

    def _get_default_value_for_type(
        self,
        col_info: Dict[str, Any],
        type_name: str,
        type_info: Dict[str, Any],
        base_type: str
    ) -> Any:
        """
        Determine a sensible default value for a type based on type registry information.
        Uses a generic approach that works for any SNMP type.
        """
        # 1. Use explicit initial value if present
        if 'initial' in col_info:
            return col_info['initial']

        # 2. For enumerated types, use the first enum value
        if type_info.get('enums'):
            enums = type_info.get('enums', [])
            if enums and isinstance(enums, list) and len(enums) > 0:
                return enums[0].get('value', 0)
            return 0

        # 3. If base_type is set, use it to determine the default
        if base_type and base_type != type_name:
            if base_type in ('Integer32', 'Integer', 'Counter32', 'Gauge32', 'Unsigned32', 'TimeTicks'):
                return 0
            elif base_type in ('OctetString', 'DisplayString'):
                return ''
            elif base_type == 'ObjectIdentifier':
                return '0.0'

        # 4. For types with null base_type, infer from constraints
        constraints = type_info.get('constraints', [])
        if constraints:
            for constraint in constraints:
                constraint_type = constraint.get('type', '')

                # ValueRangeConstraint suggests numeric type
                if constraint_type == 'ValueRangeConstraint':
                    return 0

                # ValueSizeConstraint suggests octet string or similar
                elif constraint_type == 'ValueSizeConstraint':
                    # Special case: size of 4 bytes is likely IpAddress
                    min_size = constraint.get('min', 0)
                    max_size = constraint.get('max', 0)
                    if min_size == 4 and max_size == 4:
                        return '0.0.0.0'
                    # Otherwise, it's likely an octet string
                    return ''

        # 5. Check size field as fallback
        size = type_info.get('size')
        if size:
            if isinstance(size, dict):
                size_type = size.get('type')
                if size_type == 'set':
                    allowed = size.get('allowed', [])
                    if allowed == [4]:
                        return '0.0.0.0'  # IpAddress
                    return ''  # OctetString
                elif size_type == 'range':
                    return ''  # OctetString

        # 6. Default fallback: use 0 for unknown types
        return 0


    def _register_single_table(
        self,
        mib: str,
        table_name: str,
        table_data: Dict[str, Any],
        type_registry: Dict[str, Any]
    ) -> None:
        """Register a single table by adding a row to the JSON model and PySNMP MIB tree."""
        mib_json = self.mib_jsons.get(mib)
        if not mib_json:
            self.logger.error(f"No in-memory JSON found for MIB {mib}")
            return

        table_json = mib_json.get(table_name)
        if table_json is None:
            table_json = {'rows': []}
            mib_json[table_name] = table_json
        if 'rows' not in table_json:
            table_json['rows'] = []

        # Build a new row with initial values for all columns (including index columns)
        new_row = {}
        for col_name, col_info in table_data['columns'].items():
            type_name = col_info.get('type', '')
            type_info = type_registry.get(type_name, {}) if type_name else {}
            base_type = type_info.get('base_type') or type_name
            value = self._get_default_value_for_type(col_info, type_name, type_info, base_type)
            new_row[col_name] = value

        # Set index columns to 1 (or suitable value)
        entry = table_data['entry']
        index_names = entry.get('indexes', [])
        for idx_col in index_names:
            if idx_col in new_row:
                new_row[idx_col] = 1

        # Add the row to the table JSON
        table_json['rows'].append(new_row)
        self.logger.info(f"Created row in {table_name} for MIB {mib} with {len(new_row)} columns: {new_row}")

        # --- PySNMP Table/Row/Column Registration ---
        # Import PySNMP classes
        MibTable = self.MibTable
        MibTableRow = self.MibTableRow
        MibTableColumn = self.MibTableColumn
        mib_builder = self.mib_builder
        if not (MibTable and MibTableRow and MibTableColumn and mib_builder):
            self.logger.warning(f"PySNMP MIB classes not available for table {table_name}")
            return

        table_oid = tuple(table_data['table']['oid'])
        entry_oid = tuple(entry['oid'])
        columns = table_data['columns']

        # Create Table, Row, and Column objects
        table_sym = MibTable(table_oid)
        row_sym = MibTableRow(entry_oid)
        col_syms = []
        col_names = []
        debug_oid_list = []
        self.logger.debug(f"Registering table: {table_name} OID={table_oid}")
        self.logger.debug(f"Registering row: {table_name}Entry OID={entry_oid}")
        for col_name, col_info in columns.items():
            col_oid = tuple(col_info['oid'])
            # Resolve SNMP type for the column
            type_name = col_info.get('type', '')
            type_info = type_registry.get(type_name, {}) if type_name else {}
            base_type = type_info.get('base_type') or type_name
            pysnmp_type = None
            try:
                # Try SNMPv2-SMI first
                if base_type:
                    try:
                        pysnmp_type = mib_builder.import_symbols('SNMPv2-SMI', base_type)[0]
                    except Exception:
                        try:
                            pysnmp_type = mib_builder.import_symbols('SNMPv2-TC', base_type)[0]
                        except Exception:
                            from pysnmp.proto import rfc1902
                            pysnmp_type = getattr(rfc1902, base_type, None)
                if pysnmp_type is None:
                    raise ImportError(f"Could not resolve SNMP type for base_type '{base_type}' (column {col_name})")
                col_syms.append(MibTableColumn(col_oid, pysnmp_type()))
                self.logger.debug(f"Registering column: {col_name} OID={col_oid} type={base_type}")
                debug_oid_list.append(col_oid)
            except Exception as e:
                self.logger.error(f"Error resolving SNMP type for column {col_name} in {table_name}: {e}", exc_info=True)
                continue
            col_names.append(col_name)

        self.logger.info(f"About to export table {table_name} with OIDs: table={table_oid}, row={entry_oid}, columns={debug_oid_list}")
        # Export table, row, and columns to the MIB builder
        try:
            mib_builder.export_symbols(mib, table_sym, row_sym, *col_syms)
            self.logger.info(f"Exported PySNMP table symbols for {table_name} in {mib}")
        except Exception as e:
            self.logger.error(f"Error exporting PySNMP table symbols for {table_name}: {e}", exc_info=True)
            return

        # Register a single row instance (index = 1 for all index columns)
        # Compose instance OID: entry_oid + (1,)
        instance_oid = entry_oid + (1,)
        values = [new_row.get(col_name, 0) for col_name in col_names]
        # Actually register the row instance using MibTableRow and MibTableColumn objects
        try:
            # For each column, create a MibTableColumn instance for the row
            row_instances = []
            for idx, col_name in enumerate(col_names):
                col_info = columns[col_name]
                col_oid = tuple(col_info['oid'])
                type_name = col_info.get('type', '')
                type_info = type_registry.get(type_name, {}) if type_name else {}
                base_type = type_info.get('base_type') or type_name
                pysnmp_type = None
                try:
                    if base_type:
                        try:
                            pysnmp_type = mib_builder.import_symbols('SNMPv2-SMI', base_type)[0]
                        except Exception:
                            try:
                                pysnmp_type = mib_builder.import_symbols('SNMPv2-TC', base_type)[0]
                            except Exception:
                                from pysnmp.proto import rfc1902
                                pysnmp_type = getattr(rfc1902, base_type, None)
                    if pysnmp_type is None:
                        raise ImportError(f"Could not resolve SNMP type for base_type '{base_type}' (column {col_name})")
                except Exception as e:
                    self.logger.error(f"Error resolving SNMP type for row instance column {col_name} in {table_name}: {e}", exc_info=True)
                    continue
                value = new_row.get(col_name, None)
                # Ensure value is not None and is type-appropriate
                if value is None:
                    value = self._get_default_value_for_type(col_info, type_name, type_info, base_type)
                # Compose the instance OID for this column: col_oid + (1,)
                col_instance_oid = col_oid + (1,)
                # Register as a scalar instance for the row (PySNMP expects MibScalarInstance for leafs)
                try:
                    if col_name == 'sysORIndex':
                        DEBUG = 1
                    scalar_instance = self.MibScalarInstance(col_instance_oid, (0,), pysnmp_type(value))
                    mib_builder.export_symbols(mib, scalar_instance)
                    self.logger.info(f"Registered row instance for {table_name} column {col_name} at OID {col_instance_oid} with value {value}")
                    row_instances.append(scalar_instance)
                except Exception as e:
                    self.logger.error(f"Error registering row instance for {table_name} column {col_name}: {e}", exc_info=True)
            if not row_instances:
                self.logger.warning(f"No row instances registered for {table_name} at OID {instance_oid}")
        except Exception as e:
            self.logger.error(f"Error registering row instance for {table_name}: {e}", exc_info=True)


if __name__ == "__main__":
    import sys

    try:
        agent = SNMPAgent()
        agent.run()
    except Exception as e:
        import traceback
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)