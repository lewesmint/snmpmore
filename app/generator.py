import os
import json
from typing import Dict, Any, cast, Optional
from pysnmp.smi import builder


class BehaviourGenerator:
    """Handles generation of behaviour JSON from compiled MIB Python files."""
    def __init__(self, output_dir: str = 'mock-behaviour') -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, compiled_py_path: str, mib_name: Optional[str] = None) -> str:
        """Generate behaviour JSON from a compiled MIB Python file.

        Args:
            compiled_py_path: Path to the compiled MIB .py file
            mib_name: Name of the MIB module (optional, will be parsed if not provided)

        Returns:
            Path to the generated behaviour JSON file
        """
        if mib_name is None:
            mib_name = self._parse_mib_name_from_py(compiled_py_path)
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

    def _parse_mib_name_from_py(self, compiled_py_path: str) -> str:
        """Parse the MIB name from the compiled Python file (looks for mibBuilder.exportSymbols)."""
        with open(compiled_py_path, 'r', encoding='utf-8') as f:
            for line in f:
                if 'mibBuilder.exportSymbols' in line:
                    # Example: mibBuilder.exportSymbols("MY-AGENT-MIB",
                    import re
                    m = re.search(r'mibBuilder\.exportSymbols\(["\"]([A-Za-z0-9\-_.]+)["\"]', line)
                    if m:
                        return m.group(1)
        # Fallback: use filename without extension
        return os.path.splitext(os.path.basename(compiled_py_path))[0]

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
        from pysnmp.smi import instrum, exval, builder as smi_builder
        for symbol_name, symbol_obj in mib_symbols.items():
            symbol_name_str: str = str(cast(Any, symbol_name))
            # Only process real MIB nodes (skip classes, constants, etc.)
            # Must have getName and getSyntax as bound methods (not just attributes)
            if not (hasattr(symbol_obj, 'getName') and hasattr(symbol_obj, 'getSyntax')):
                continue
            # Ensure getName is a method bound to the instance
            try:
                oid = symbol_obj.getName()
                syntax_obj = symbol_obj.getSyntax()
                syntax = syntax_obj.__class__.__name__
                access = getattr(symbol_obj, 'getMaxAccess', lambda: 'unknown')()
            except TypeError:
                continue

            # Extract type metadata (base type, constraints, enums)
            type_info = self._extract_type_info(syntax_obj, syntax)

            # Provide sensible default initial values based on type
            initial_value = self._get_default_value_from_type_info(type_info, symbol_name_str)
            dynamic_func = self._get_dynamic_function(symbol_name_str)

            result[symbol_name_str] = {
                'oid': oid,
                'type': syntax,
                'type_info': type_info,
                'access': access,
                'initial': initial_value,
                'dynamic_function': dynamic_func
            }
        return result

    def _extract_type_info(self, syntax_obj: Any, syntax_name: str) -> Dict[str, Any]:
        """Extract detailed type information from a syntax object.

        Returns:
            Dictionary with 'base_type', 'enums' (if applicable), 'constraints', etc.
        """
        from pysnmp.proto.rfc1902 import Integer32, Integer, OctetString, ObjectIdentifier, IpAddress, Counter32, Counter64, Gauge32, Unsigned32, TimeTicks

        # Determine base type by checking the class hierarchy (MRO)
        # For TextualConventions, we want the actual base SNMP type, not the TC name
        base_type = syntax_name

        # Get the class hierarchy
        mro = type(syntax_obj).__mro__

        # Look for the first base SNMP type in the hierarchy by checking class names
        # We check by name because the classes might be from different imports
        base_type_names = ['ObjectIdentifier', 'OctetString', 'Integer32', 'Integer', 'IpAddress', 'Counter32', 'Counter64', 'Gauge32', 'Unsigned32', 'TimeTicks']
        for cls in mro:
            cls_name = cls.__name__
            if cls_name in base_type_names:
                base_type = cls_name
                break

        type_info: Dict[str, Any] = {
            'base_type': base_type,
            'enums': None,
            'constraints': None
        }

        # Extract named values (enumerations)
        if hasattr(syntax_obj, 'namedValues') and syntax_obj.namedValues:
            enums = {}
            for name in syntax_obj.namedValues:
                value = syntax_obj.namedValues[name]
                enums[name] = value
            if enums:
                type_info['enums'] = enums

        # Extract constraints
        if hasattr(syntax_obj, 'subtypeSpec') and syntax_obj.subtypeSpec:
            constraints = []
            try:
                # Try to get values attribute (for ConstraintsUnion)
                if hasattr(syntax_obj.subtypeSpec, 'values'):
                    for constraint in syntax_obj.subtypeSpec.values:
                        constraint_info = str(constraint)
                        constraints.append(constraint_info)
                else:
                    # For other constraint types, just convert to string
                    constraints.append(str(syntax_obj.subtypeSpec))
            except Exception:
                # If we can't extract constraints, just skip them
                pass
            if constraints:
                type_info['constraints'] = constraints

        return type_info

    def _get_default_value_from_type_info(self, type_info: Dict[str, Any], symbol_name: str) -> Any:
        """Get a sensible default value based on type info and symbol name."""
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
        elif symbol_name == 'ifNumber':
            return 1  # Match the number of interface rows we'll create

        base_type = type_info.get('base_type', '')
        enums = type_info.get('enums')

        # If it has enums, use a sensible default enum value
        if enums:
            # Special cases for known enum fields
            if symbol_name in ('ifAdminStatus', 'ifOperStatus'):
                return 2  # down(2)
            elif symbol_name == 'ifType':
                return 6  # ethernetCsmacd(6)
            elif symbol_name.endswith('Status') and 'notInService' in enums:
                # RowStatus should be active(1) for existing rows
                return 1
            elif 'unknown' in enums:
                return enums['unknown']
            elif 'other' in enums:
                return enums['other']
            else:
                # Return the first valid enum value (not 0 if possible)
                for name, value in enums.items():
                    if value != 0:
                        return value
                # If all are 0 or only one value, return it
                return list(enums.values())[0] if enums else 0

        # Type-based defaults
        if base_type in ('DisplayString', 'OctetString'):
            # Check if this is a DateAndTime type
            if 'Date' in symbol_name or 'Time' in symbol_name:
                # Return hex string for 2000-01-01 00:00:00.0
                return '07D0010100000000'
            return 'unset'
        elif base_type == 'ObjectIdentifier':
            return '0.0'
        elif base_type in ('Integer32', 'Integer', 'Gauge32', 'Unsigned32'):
            return 0
        elif base_type in ('Counter32', 'Counter64'):
            return 0
        elif base_type == 'IpAddress':
            return '0.0.0.0'
        elif base_type == 'TimeTicks':
            return 0
        else:
            return None

    def _get_default_value(self, syntax: str, symbol_name: str) -> Any:
        """Legacy method - kept for compatibility."""
        # This is now handled by _get_default_value_from_type_info
        # but kept as fallback
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
            return 'unset'
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
