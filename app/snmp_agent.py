"""
SNMPAgent: Main orchestrator for the SNMP agent (initial workflow).
"""
from typing import cast
from app.app_logger import AppLogger
from app.app_config import AppConfig
from app.compiler import MibCompiler
from app.type_registry import TypeRegistry
import subprocess
import os
from pathlib import Path
import json
import time
from typing import Any, Dict, Optional

class SNMPAgent:

    def __init__(self, host: str = '127.0.0.1', port: int = 161, config_path: str = 'agent_config.yaml') -> None:
        # Set up logging and config
        if not AppLogger._configured:
            self.app_config = AppConfig(config_path)
            AppLogger.configure(self.app_config)
        else:
            self.app_config = AppConfig(config_path)
        self.logger = AppLogger.get(__name__)
        self.config_path = config_path
        self.host = host
        self.port = port
        self.snmpEngine: Optional[Any] = None
        self.mibBuilder: Optional[Any] = None
        self.mib_jsons: Dict[str, Dict[str, Any]] = {}
        # Track agent start time for sysUpTime
        self.start_time = time.time()

    def run(self) -> None:
        self.logger.info("Starting SNMP Agent setup workflow...")
        # Compile MIBs and generate behavior JSONs as before
        mibs = cast(list[str], self.app_config.get('mibs', []))
        compiled_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'compiled-mibs'))
        json_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mock-behaviour'))
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
                self.logger.error(f"Failed to compile {mib_path}: {e}")
                continue

        # Build and export the canonical type registry
        from app.type_registry import TypeRegistry
        type_registry = TypeRegistry(Path(compiled_dir))
        type_registry.build()
        type_registry.export_to_json("data/types.json")
        self.logger.info(f"Exported type registry to data/types.json with {len(type_registry.registry)} types.")

        # Validate types
        self.logger.info("Validating type registry...")
        try:
            subprocess.run(['python3', 'tools/validate_types.py', 'data/types.json'], check=True)
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
                self.logger.error(f"Failed to generate behavior JSON for {py_path}: {e}")

        # Load behavior JSONs for SNMP serving
        for mib in mibs:
            json_path = os.path.join(json_dir, f'{mib}_behaviour.json')
            if os.path.exists(json_path):
                with open(json_path, 'r') as jf:
                    self.mib_jsons[mib] = json.load(jf)
        self.logger.info("Loaded behavior JSONs for SNMP serving.")

        # Setup SNMP engine and transport
        self._setup_snmp_engine(compiled_dir)
        if self.snmpEngine is not None:
            self._setup_transport()
            self._setup_community()
            self._setup_responders()
            self._register_mib_objects()
            self.logger.info("SNMP Agent is now listening for SNMP requests.")
            # Block and serve SNMP requests using pysnmp dispatcher (old agent.py style)
            try:
                self.logger.info("Entering SNMP event loop...")
                self.snmpEngine.transport_dispatcher.job_started(1)
                self.snmpEngine.transport_dispatcher.run_dispatcher()
            except KeyboardInterrupt:
                self.logger.info('Shutting down agent')
            except Exception as e:
                self.logger.error(f"SNMP event loop error: {e}")
            finally:
                self.snmpEngine.transport_dispatcher.close_dispatcher()
        else:
            self.logger.error("snmpEngine is not initialized. SNMP agent will not start.")

    def _setup_snmp_engine(self, compiled_dir: str) -> None:
        from pysnmp.entity import engine
        from pysnmp.smi import builder
        self.snmpEngine = engine.SnmpEngine()
        self.mibBuilder = None
        if self.snmpEngine is not None:
            self.mibBuilder = self.snmpEngine.get_mib_builder()
            if self.mibBuilder is not None:
                self.mibBuilder.add_mib_sources(builder.DirMibSource(compiled_dir))

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
            udp.UdpTransport().open_server_mode((self.host, self.port))
        )

    def _setup_community(self) -> None:
        from pysnmp.entity import config
        if self.snmpEngine is None:
            raise RuntimeError("snmpEngine is not initialized.")
        config.add_v1_system(self.snmpEngine, 'my-area', 'public')
        config.add_context(self.snmpEngine, '')
        config.add_vacm_group(self.snmpEngine, 'mygroup', 2, 'my-area')
        config.add_vacm_view(self.snmpEngine, 'restrictedView', 1, (1, 3, 6, 1), '')
        config.add_vacm_view(self.snmpEngine, 'restrictedView', 2, (1, 3, 6, 1, 6, 3), '')
        config.add_vacm_access(
            self.snmpEngine,
            'mygroup', '', 2, 'noAuthNoPriv', 'exact',
            'restrictedView', 'restrictedView', 'restrictedView'
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
        if self.mibBuilder is None:
            self.logger.error("mibBuilder is not initialized.")
            return

        # Load the type registry from the exported JSON file
        type_registry_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'types.json')
        try:
            with open(type_registry_path, 'r') as f:
                type_registry = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load type registry: {e}")
            type_registry = {}

        for mib, mib_json in self.mib_jsons.items():
            scalar_symbols = []
            for name, info in mib_json.items():
                if not isinstance(info, dict):
                    continue
                access = info.get('access')
                if access in ['not-accessible', 'accessible-for-notify']:
                    continue
                oid = info.get('oid')
                oid_value = tuple(oid) if isinstance(oid, list) else ()
                value = info.get('current') if 'current' in info else info.get('initial')
                type_name = info.get('type')
                type_info = type_registry.get(type_name, {})
                base_type = type_info.get('base_type') or type_name

                # Skip if we don't have a valid type name
                if not base_type or not isinstance(base_type, str):
                    self.logger.warning(f"Skipping {name}: invalid type '{type_name}'")
                    continue

                # Special handling for sysUpTime - use actual system uptime
                if name == 'sysUpTime':
                    # Calculate uptime in hundredths of a second (TimeTicks format)
                    uptime_seconds = time.time() - self.start_time
                    value = int(uptime_seconds * 100)
                    self.logger.debug(f"Setting sysUpTime to {value} (uptime: {uptime_seconds:.2f}s)")

                # Handle None values with sensible defaults based on type
                if value is None:
                    if base_type in ['Integer32', 'Integer', 'Gauge32', 'Counter32', 'Counter64', 'TimeTicks', 'Unsigned32']:
                        value = 0
                    elif base_type in ['OctetString', 'DisplayString']:
                        value = ''
                    elif base_type == 'ObjectIdentifier':
                        value = '0.0'
                    else:
                        # Skip objects we can't provide a default for
                        self.logger.warning(f"Skipping {name}: no value and no default for type '{base_type}'")
                        continue

                mib_scalar = None
                mib_scalar_instance = None
                # Try to resolve the SNMP type class dynamically
                pysnmp_type = None
                try:
                    # Try to import the base type from SNMPv2-SMI or SNMPv2-TC
                    try:
                        pysnmp_type = self.mibBuilder.import_symbols('SNMPv2-SMI', base_type)[0]
                    except Exception:
                        try:
                            pysnmp_type = self.mibBuilder.import_symbols('SNMPv2-TC', base_type)[0]
                        except Exception:
                            # Fallback to pysnmp.proto.rfc1902 (correct module for base types)
                            from pysnmp.proto import rfc1902
                            pysnmp_type = getattr(rfc1902, base_type, None)
                    if pysnmp_type is None:
                        raise ImportError(f"Could not resolve SNMP type for base_type '{base_type}' (symbol {name})")
                    MibScalar = self.mibBuilder.import_symbols('SNMPv2-SMI', 'MibScalar')[0]
                    MibScalarInstance = self.mibBuilder.import_symbols('SNMPv2-SMI', 'MibScalarInstance')[0]
                    mib_scalar = MibScalar(oid_value, pysnmp_type(value))
                    mib_scalar_instance = MibScalarInstance(oid_value, (0,), pysnmp_type(value))
                    self.logger.info(f"Successfully registered {name} (type {type_name}, base {base_type})")
                except Exception as e:
                    self.logger.error(f"Error registering {name} (type {type_name}, base {base_type}): {e}")
                if mib_scalar:
                    scalar_symbols.append(mib_scalar)
                if mib_scalar_instance:
                    scalar_symbols.append(mib_scalar_instance)
                if not type_info:
                    self.logger.warning(f"Type '{type_name}' for symbol '{name}' not found in type registry; used fallback.")
            if scalar_symbols:
                try:
                    self.mibBuilder.export_symbols(mib, *scalar_symbols)
                    self.logger.info(f"Registered {len(scalar_symbols)} objects for {mib}")
                except Exception as e:
                    self.logger.error(f"Error exporting symbols for {mib}: {e}")

if __name__ == "__main__":
    import sys
    try:
        agent = SNMPAgent()
        agent.run()
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
