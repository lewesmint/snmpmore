# SNMP Agent - Remaining Fixes

## Current State
The agent is mostly working. Most tables load successfully. The type_info system in `app/generator.py` now correctly extracts base types from TextualConventions and stores them in the behaviour JSON files.

**Tables Loading Successfully:**
- ifTable, ifXTable, ifTestTable
- hrStorageTable, hrDeviceTable, hrProcessorTable, hrNetworkTable
- hrPrinterTable, hrDiskStorageTable, hrPartitionTable
- hrFSTable, hrSWRunTable, hrSWRunPerfTable, hrSWInstalledTable
- coiAlarmActiveTable

## Remaining Issues

### 1. RowStatus Columns Failing (Priority: Medium)
**Affected Tables:** ifStackTable, ifRcvAddressTable

**Problem:** RowStatus columns fail with `WrongValueError` when writing value `1` (active).

**Root Cause:** The type_map in `app/agent.py` line 396 maps `RowStatus` to `Integer32`, but pysnmp's RowStatus type has special validation. Need to import and use the actual `RowStatus` class from SNMPv2-TC.

**Files:** `app/agent.py` lines 396, 471-473

**Fix Approach:** 
1. Import RowStatus from pysnmp: `from pysnmp.smi.rfc1902 import RowStatus` (or find correct import path)
2. Update type_map to use the actual RowStatus class
3. Remove the special handling in `_get_snmp_value` that returns `Integer32(2)` for RowStatus

### 2. Verify Enum Values (Priority: Low)
**Task:** Verify all enum fields in HOST-RESOURCES-MIB have valid non-zero values.

Check these fields in `mock-behaviour/HOST-RESOURCES-MIB_behaviour.json`:
- hrDeviceStatus
- hrFSAccess  
- hrDiskStorageAccess
- hrDiskStorageMedia
- hrPrinterStatus

The generator logic in `app/generator.py` `_get_default_value_from_type_info()` should already handle this, but verify with snmpwalk.

### 3. Socket Port 6060 Conflict (Priority: Low)
**Problem:** REST API fails to bind to port 6060 (already in use).

**Fix:** Kill the existing process using port 6060, or change the port in the agent configuration.

### 4. Duplicate JSON Write Messages (Priority: Low)
**Problem:** Each behaviour JSON file is written twice during generation.

**Location:** `app/generator.py` - check where `generate()` is called

## Key Files
- `app/agent.py` - Main SNMP agent, type mapping, value conversion
- `app/generator.py` - Generates behaviour JSON from compiled MIBs
- `mock-behaviour/*.json` - Behaviour JSON files with type_info

## Testing
```powershell
# Regenerate JSON and run agent
Remove-Item mock-behaviour\*.json
python .\run_agent_with_rest.py

# Test with snmpwalk
snmpwalk -v2c -c public localhost:11161
```

