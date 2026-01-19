import os
import json
from typing import Dict, Any, cast
from pysnmp.smi import builder


class BehaviourGenerator:
    """Handles generation of behaviour JSON from compiled MIB Python files."""
    def __init__(self, output_dir: str = 'mock-behaviour') -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, compiled_py_path: str, mib_name: str) -> str:
        """Generate behaviour JSON from a compiled MIB Python file.

        Args:
            compiled_py_path: Path to the compiled MIB .py file
            mib_name: Name of the MIB module

        Returns:
            Path to the generated behaviour JSON file
        """
        json_path = os.path.join(self.output_dir, f'{mib_name}_behaviour.json')

        if os.path.exists(json_path):
            return json_path

        # Extract MIB information
        info = self._extract_mib_info(compiled_py_path, mib_name)

        # Write to JSON file
        with open(json_path, 'w') as f:
            json.dump(info, f, indent=2)

        print(f'Behaviour JSON written to {json_path}')
        return json_path

    def _extract_mib_info(self, mib_py_path: str, mib_name: str) -> Dict[str, Any]:
        """Extract MIB symbol information from a compiled MIB Python file.

        Args:
            mib_py_path: Path to the compiled MIB .py file
            mib_name: Name of the MIB module

        Returns:
            Dictionary mapping symbol names to their metadata
        """
        mibBuilder = builder.MibBuilder()
        mibBuilder.add_mib_sources(builder.DirMibSource(os.path.dirname(mib_py_path)))
        mibBuilder.load_modules(mib_name)
        mib_symbols = mibBuilder.mibSymbols[mib_name]

        result: Dict[str, Any] = {}
        for symbol_name, symbol_obj in mib_symbols.items():
            symbol_name_str: str = str(cast(Any, symbol_name))
            # Only process scalars and columns
            if hasattr(cast(Any, symbol_obj), 'getName') and hasattr(cast(Any, symbol_obj), 'getSyntax'):
                oid = cast(Any, symbol_obj).getName()
                syntax = cast(Any, symbol_obj).getSyntax().__class__.__name__
                access = getattr(cast(Any, symbol_obj), 'getMaxAccess', lambda: 'unknown')()

                # Provide sensible default initial values based on type
                initial_value = self._get_default_value(syntax, symbol_name_str)
                dynamic_func = self._get_dynamic_function(symbol_name_str)

                result[symbol_name_str] = {
                    'oid': oid,
                    'type': syntax,
                    'access': access,
                    'initial': initial_value,
                    'dynamic_function': dynamic_func
                }
        return result

    def _get_default_value(self, syntax: str, symbol_name: str) -> Any:
        """Get a sensible default value based on the type and symbol name."""
        # Special cases for well-known system objects
        if symbol_name == 'sysDescr':
            return 'Simple Python SNMP Agent - Demo System'
        elif symbol_name == 'sysObjectID':
            return '1.3.6.1.4.1.99999'
        elif symbol_name == 'sysContact':
            return 'Admin <admin@example.com>'
        elif symbol_name == 'sysName':
            return 'my-pysnmp-agent'
        elif symbol_name == 'sysLocation':
            return 'Development Lab'
        elif symbol_name == 'sysUpTime':
            return None  # Dynamic, handled by uptime function

        # Type-based defaults
        if syntax in ('DisplayString', 'OctetString'):
            return ''
        elif syntax == 'ObjectIdentifier':
            return '0.0'
        elif syntax in ('Integer32', 'Integer', 'Gauge32', 'Unsigned32'):
            return 0
        elif syntax in ('Counter32', 'Counter64'):
            return 0
        elif syntax == 'IpAddress':
            return '0.0.0.0'
        elif syntax == 'TimeTicks':
            return 0
        else:
            return None

    def _get_dynamic_function(self, symbol_name: str) -> Any:
        """Determine if this symbol should use a dynamic function."""
        if symbol_name == 'sysUpTime':
            return 'uptime'
        return None
