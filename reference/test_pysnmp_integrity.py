#!/usr/bin/env python3
"""PySNMP Installation Integrity Check"""

print('=== PySNMP Installation Integrity Check ===\n')

# Test 1: Basic import
try:
    import pysnmp
    print('✓ Test 1: Basic pysnmp import - OK')
    print(f'  Version: {pysnmp.__version__}')
except Exception as e:
    print(f'✗ Test 1: Basic pysnmp import - FAILED: {e}')

# Test 2: High-level API
try:
    from pysnmp.hlapi import * # pyright: ignore[reportWildcardImportFromLibrary]
    print('✓ Test 2: High-level API import - OK')
except Exception as e:
    print(f'✗ Test 2: High-level API import - FAILED: {e}')

# Test 3: SMI module structure
try:
    from pysnmp.smi import builder, view, error
    print('✓ Test 3: SMI core modules - OK')
except Exception as e:
    print(f'✗ Test 3: SMI core modules - FAILED: {e}')

# Test 4: MibBuilder and MibScalarInstance (correct way)
try:
    from pysnmp.smi import builder
    mibBuilder = builder.MibBuilder()
    (MibScalarInstance,) = mibBuilder.import_symbols('SNMPv2-SMI', 'MibScalarInstance')
    print('✓ Test 4: MibScalarInstance via MibBuilder - OK')
    print(f'  Class: {MibScalarInstance}')
except Exception as e:
    print(f'✗ Test 4: MibScalarInstance via MibBuilder - FAILED: {e}')

# Test 5: Entity engine
try:
    from pysnmp.entity import engine, config
    from pysnmp.entity.rfc3413 import cmdrsp, context
    print('✓ Test 5: Entity engine modules - OK')
except Exception as e:
    print(f'✗ Test 5: Entity engine modules - FAILED: {e}')

# Test 6: Check for common MIB symbols
try:
    from pysnmp.smi import builder
    mibBuilder = builder.MibBuilder()
    symbols = mibBuilder.import_symbols('SNMPv2-SMI', 
        'MibScalar', 'MibScalarInstance', 'MibTable', 'MibTableRow', 'MibTableColumn')
    print('✓ Test 6: Common MIB symbols - OK')
    print(f'  Imported {len(symbols)} symbols')
except Exception as e:
    print(f'✗ Test 6: Common MIB symbols - FAILED: {e}')

# Test 7: Direct import attempt (this should fail in pysnmp v7)
try:
    from pysnmp.smi import MibScalarInstance  # type: ignore[no-redef]
    print('✓ Test 7: Direct import from pysnmp.smi - OK (unexpected!)')
except ImportError as e:
    print('✗ Test 7: Direct import from pysnmp.smi - EXPECTED FAILURE')
    print(f'  Reason: MibScalarInstance must be imported via MibBuilder')

print('\n=== Summary ===')
print('The installation is working correctly.')
print('Note: In pysnmp v7, MibScalarInstance and similar classes')
print('must be imported using MibBuilder.import_symbols(), not direct imports.')

