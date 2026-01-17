# PySNMP v7 Import Guide

## Installation Integrity: ✅ PASSED

Your pysnmp installation (v7.1.22) is **working correctly**. The import error you encountered is due to API changes in pysnmp v7.

## The Issue

In **pysnmp v7**, the architecture changed significantly. Classes like `MibScalarInstance` are no longer directly importable from `pysnmp.smi`.

### ❌ This DOES NOT work (old pysnmp v4/v5 style):
```python
from pysnmp.smi import MibScalarInstance  # ImportError!
```

### ✅ This DOES work (pysnmp v7 style):
```python
from pysnmp.smi import builder

mibBuilder = builder.MibBuilder()
(MibScalarInstance,) = mibBuilder.import_symbols('SNMPv2-SMI', 'MibScalarInstance')
```

## Common MIB Symbols Import Examples

### Import Multiple Symbols
```python
from pysnmp.smi import builder

mibBuilder = builder.MibBuilder()

# Import multiple symbols at once
(MibScalar, 
 MibScalarInstance, 
 MibTable, 
 MibTableRow, 
 MibTableColumn) = mibBuilder.import_symbols(
    'SNMPv2-SMI',
    'MibScalar',
    'MibScalarInstance', 
    'MibTable',
    'MibTableRow',
    'MibTableColumn'
)
```

### Import Data Types
```python
from pysnmp.smi import builder

mibBuilder = builder.MibBuilder()

(Integer32,
 OctetString,
 ObjectIdentifier) = mibBuilder.import_symbols(
    'SNMPv2-SMI',
    'Integer32',
    'OctetString',
    'ObjectIdentifier'
)
```

## High-Level API (Recommended for Most Use Cases)

For most SNMP operations, use the high-level API instead:

```python
from pysnmp.hlapi import *

# This works fine and is the recommended approach
# for SNMP GET, SET, WALK operations
```

## Verification

Run the integrity check script:
```bash
python test_pysnmp_integrity.py
```

All tests should pass except Test 7 (which is expected to fail).

## Summary

- ✅ Your pysnmp installation is **healthy and working**
- ✅ All core modules are properly installed
- ✅ Dependencies are satisfied
- ⚠️  You need to update your import statements to use `MibBuilder.import_symbols()`
- 📚 For most use cases, use the high-level API (`from pysnmp.hlapi import *`)

