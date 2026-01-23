# SNMP Agent Startup Warnings and Errors Explained

This document explains the warnings and errors observed when running the SNMP agent (as of 2026-01-22) in this project. These messages are typical when loading and registering MIB tables with PySNMP and custom MIBs.

## Summary of Observed Messages

- **INFO**: MIBs loaded from behaviour JSON and compiled MIBs.
- **Warning/Error**: Table registration failures for various MIB tables (e.g., `ifTable`, `ifStackTable`, `hrStorageTable`, etc.).
- **Details**: Warnings include missing symbols, unknown base types, and value model incompatibilities.

---

## Common Warning/Failure Patterns

### 1. "Could not register table ...: No symbol ..."
- **Example**: `Warning: Could not register table ifTable: No symbol __IF-MIB::ifIndex ...`
- **Meaning**: The agent could not find the specified symbol in the compiled MIBs. This usually means:
  - The symbol is missing from the compiled MIB Python files.
  - The MIB was not fully or correctly compiled.
  - The symbol name is incorrect or not exported.
- **Impact**: The table cannot be registered, so SNMP operations for this table will not work.
- **Remediation**:
  - Check that the MIB is present in `compiled-mibs/` and contains the required symbol.
  - Recompile the MIB if necessary.

### 2. "Failed columns: ... (unknown base type after TC resolution)"
- **Example**: `ifStackStatus: RowStatus (unknown base type after TC resolution)`
- **Meaning**: The agent could not resolve the base type for a textual convention (TC) used in the MIB. This can happen if:
  - The TC is not defined in the loaded MIBs.
  - The MIB dependencies are missing or not loaded in the correct order.
- **Impact**: The affected column(s) cannot be registered, so SNMP operations for these columns will not work.
- **Remediation**:
  - Ensure all dependent MIBs (especially those defining TCs) are compiled and loaded.
  - Check for typos or missing imports in the MIB source.

### 3. "base type supported but value model incompatible: MIB subtree ... not registered at MibScalar(...)"
- **Example**: `ifStackHigherLayer: InterfaceIndexOrZero -> Integer32 (base type supported but value model incompatible: MIB subtree ... not registered at MibScalar(...))`
- **Meaning**: The base type is recognized, but the value model (e.g., constraints, subtypes, or OIDs) could not be matched to a registered MIB object. This often means:
  - The referenced OID or object is missing from the compiled MIBs.
  - The MIB hierarchy is incomplete.
- **Impact**: The column cannot be registered.
- **Remediation**:
  - Check that all referenced OIDs and objects are present in the compiled MIBs.
  - Recompile or fix the MIBs as needed.

### 4. "unknown base type after TC resolution"
- **Example**: `coiAlarmObjectEntPhyIndex: EntPhysicalIndexOrZero (unknown base type after TC resolution)`
- **Meaning**: Similar to (2), the agent cannot resolve the base type for a textual convention.
- **Remediation**: See (2).

---

## General Causes
- **Missing or incomplete compiled MIBs**: Not all required MIBs are present or correctly compiled in `compiled-mibs/`.
- **MIB dependency order**: Some MIBs depend on others (e.g., TCs, base types). All dependencies must be loaded first.
- **Incorrect or missing symbol exports**: The required symbols are not exported in the compiled MIB Python files.
- **PySNMP limitations**: Some complex MIB constructs or TCs may not be fully supported by PySNMP or the MIB compiler.

## What These Warnings Mean for the Agent
- **The agent is running and serving SNMP/REST requests.**
- **Some tables/columns are not available** due to registration failures. SNMP operations on these will fail or be incomplete.
- **No Python exceptions or crashes**: These are not fatal errors, but indicate incomplete SNMP support.

## How to Fix or Investigate Further
1. **Check compiled MIBs**: Ensure all required MIBs are present in `compiled-mibs/`.
2. **Recompile MIBs**: Use the MIB compiler to regenerate Python files for any missing or problematic MIBs.
3. **Check MIB dependencies**: Make sure all dependencies (especially for TCs) are compiled and loaded.
4. **Review symbol names**: Ensure the symbol names in the MIBs match those expected by the agent.
5. **Consult PySNMP documentation**: Some MIB features may not be fully supported.

## Example: ifTable Registration Failure
- **Message**: `Warning: Could not register table ifTable: No symbol __IF-MIB::ifIndex ...`
- **Diagnosis**: The symbol `ifIndex` is missing from the compiled IF-MIB.
- **Action**: Check `compiled-mibs/IF-MIB.py` for `ifIndex`. If missing, recompile IF-MIB.

## Example: hrStorageTable Column Failure
- **Message**: `hrStorageIndex: Integer32 -> Integer32 (base type supported but value model incompatible: MIB subtree ... not registered at MibScalar(...))`
- **Diagnosis**: The OID for `hrStorageIndex` is missing or not registered.
- **Action**: Check that all referenced OIDs are present in the compiled MIBs.

---

## Conclusion
These warnings are common when working with custom or complex MIBs in PySNMP. They indicate missing or incompatible MIB definitions, but do not prevent the agent from running. To resolve, ensure all MIBs and their dependencies are correctly compiled and loaded.

---

*Last updated: 2026-01-22*
