import sys
import os
import json
from typing import Dict, Any, cast
from pysnmp.smi import builder

def check_imported_mibs(mib_txt_path: str, compiled_dir: str) -> None:
    """Parse IMPORTS section of the MIB text file and warn about missing compiled MIBs."""
    if not os.path.exists(mib_txt_path):
        print(f"WARNING: MIB source file {mib_txt_path} not found for import check.")
        return
    with open(mib_txt_path, 'r') as f:
        lines = f.readlines()
    in_imports = False
    imported_mibs = set()
    for line in lines:
        l = line.strip()
        if l.startswith('IMPORTS'):
            in_imports = True
            continue
        if in_imports:
            if ';' in l:
                in_imports = False
                l = l.split(';')[0]
            # Look for FROM <MIB-NAME>
            parts = l.split('FROM')
            if len(parts) == 2:
                mib_name = parts[1].strip().rstrip(';')
                # Remove trailing comments
                mib_name = mib_name.split()[0]
                imported_mibs.add(mib_name)
    # Check for missing compiled MIBs
    for mib in imported_mibs:
        py_path = os.path.join(compiled_dir, f"{mib}.py")
        if not os.path.exists(py_path):
            print(f"WARNING: MIB imports {mib}, but {py_path} is missing. Compile this MIB to avoid runtime errors.")

def extract_mib_info(mib_py_path: str, mib_name: str) -> Dict[str, Any]:
    mibBuilder = builder.MibBuilder()
    mibBuilder.add_mib_sources(builder.DirMibSource(os.path.dirname(mib_py_path)))
    mibBuilder.load_modules(mib_name)
    mib_symbols = mibBuilder.mibSymbols[mib_name]
    result: Dict[str, Any] = {}

    # Known SNMP base types and common textual conventions
    known_types = {
        'DisplayString', 'OctetString', 'Integer', 'Integer32', 'Counter32', 'Counter64', 'Gauge32', 'TimeTicks',
        'IpAddress', 'Unsigned32', 'ObjectIdentifier', 'Bits', 'TruthValue', 'PhysAddress', 'DateAndTime',
        'AutonomousType', 'OwnerString', 'KBytes', 'ProductID', 'InterfaceIndexOrZero', 'EntPhysicalIndexOrZero',
        'CoiAlarmObjectTypeClass', 'InetAddressType', 'InetAddress', 'InetPortNumber', 'InternationalDisplayString',
        'RowPointer', 'RowStatus', 'TestAndIncr', 'TimeStamp', 'MacAddress', 'VariablePointer', 'TimeInterval',
        'TDomain', 'TAddress', 'StorageType', 'TextualConvention', 'NoneType'
    }

    missing_types = set()
    for symbol_name, symbol_obj in mib_symbols.items():
        # Only process scalars and columns, skip classes/types
        if not hasattr(symbol_obj, '__class__') or isinstance(symbol_obj, type):
            continue
        if hasattr(symbol_obj, 'getName') and hasattr(symbol_obj, 'getSyntax'):
            oid = symbol_obj.getName()
            syntax = symbol_obj.getSyntax().__class__.__name__
            access = getattr(symbol_obj, 'getMaxAccess', lambda: 'unknown')()
            result[symbol_name] = {
                'oid': oid,
                'type': syntax,
                'access': access,
                'initial': None,
                'dynamic_function': None
            }
            if syntax not in known_types:
                missing_types.add(syntax)

    if missing_types:
        print(f"WARNING: The following types are used but not mapped in known_types: {', '.join(sorted(missing_types))}")
        print("You may need to add/compile additional MIBs or extend your type map.")

    # Check for missing compiled MIB dependencies
    compiled_dir = os.path.dirname(mib_py_path)
    for t in missing_types:
        dep_py = os.path.join(compiled_dir, f"{t}.py")
        if not os.path.exists(dep_py):
            print(f"WARNING: Possible missing compiled MIB dependency: {dep_py}")

    return result

def main() -> None:
    if len(sys.argv) != 4:
        print('Usage: python mib_to_json.py <compiled_mib_py> <mib_name> <mib_txt_path>')
        sys.exit(1)
    mib_py_path = sys.argv[1]
    mib_name = sys.argv[2]
    mib_txt_path = sys.argv[3]
    compiled_dir = os.path.dirname(mib_py_path)
    check_imported_mibs(mib_txt_path, compiled_dir)
    info = extract_mib_info(mib_py_path, mib_name)

    # Ensure mock-behaviour directory exists
    os.makedirs('mock-behaviour', exist_ok=True)

    json_path = f'mock-behaviour/{mib_name}_behaviour.json'
    with open(json_path, 'w') as f:
        json.dump(info, f, indent=2)
    print(f'Behaviour JSON written to {json_path}')

if __name__ == '__main__':
    main()
