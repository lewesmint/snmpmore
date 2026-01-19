import sys
import os
import json
from typing import Dict, Any, cast
from pysnmp.smi import builder

def extract_mib_info(mib_py_path: str, mib_name: str) -> Dict[str, Any]:
    mibBuilder = builder.MibBuilder()
    mibBuilder.add_mib_sources(builder.DirMibSource(os.path.dirname(mib_py_path)))
    mibBuilder.load_modules(mib_name)
    mib_symbols = mibBuilder.mibSymbols[mib_name]
    result: Dict[str, Any] = {}
    for symbol_name, symbol_obj in mib_symbols.items():
        # Only process scalars and columns
        if hasattr(cast(Any, symbol_obj), 'getName') and hasattr(cast(Any, symbol_obj), 'getSyntax'):  # Scalar or Column
            oid = cast(Any, symbol_obj).getName()
            syntax = cast(Any, symbol_obj).getSyntax().__class__.__name__
            access = getattr(cast(Any, symbol_obj), 'getMaxAccess', lambda: 'unknown')()
            result[symbol_name] = {
                'oid': oid,
                'type': syntax,
                'access': access,
                'initial': None,  # To be filled by user or default
                'dynamic_function': None  # To be filled by user if needed
            }
    return result

def main() -> None:
    if len(sys.argv) != 3:
        print('Usage: python mib_to_json.py <compiled_mib_py> <mib_name>')
        sys.exit(1)
    mib_py_path = sys.argv[1]
    mib_name = sys.argv[2]
    info = extract_mib_info(mib_py_path, mib_name)

    # Ensure mock-behaviour directory exists
    os.makedirs('mock-behaviour', exist_ok=True)

    json_path = f'mock-behaviour/{mib_name}_behaviour.json'
    with open(json_path, 'w') as f:
        json.dump(info, f, indent=2)
    print(f'Behaviour JSON written to {json_path}')

if __name__ == '__main__':
    main()
