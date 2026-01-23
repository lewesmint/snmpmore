# SNMP Agent Errors and Warnings Explained

## 1. Python Import Errors

### Example
```
Traceback (most recent call last):
  File "/Users/mintz/code/snmpmore/app/agent.py", line 25, in <module>
    from app.app_config import AppConfig
ModuleNotFoundError: No module named 'app'
```
**Cause:**
- The Python interpreter cannot find the `app` module. This usually happens if you run the script from the wrong working directory or the `PYTHONPATH` is not set correctly.

**Solution:**
- Run scripts from the project root directory.
- Use `python -m app.agent` from the root, or set `PYTHONPATH` to include the project root.

---

## 2. SNMP Agent Runtime Warnings

### Table Registration Warnings
```
WARNING app.agent [MainThread] Could not register table ifTable: No symbol __IF-MIB::ifIndex at <pysnmp.smi.builder.MibBuilder object ...>
WARNING app.agent [MainThread] Could not register table ifStackTable: No symbol __IF-MIB::ifStackStatus ...
WARNING app.agent [MainThread] Could not register table ifRcvAddressTable: No symbol __IF-MIB::ifRcvAddressAddress ...
WARNING app.agent [MainThread] Could not register table hrFSTable: No symbol __HOST-RESOURCES-MIB::hrFSLastFullBackupDate ...
WARNING app.agent [MainThread] Could not register table hrSWInstalledTable: No symbol __HOST-RESOURCES-MIB::hrSWInstalledDate ...
WARNING app.agent [MainThread] Could not register table coiAlarmActiveTable: No symbol __CISCO-ALARM-MIB::coiAlarmObjectEntPhyIndex ...
```
**Cause:**
- The agent could not find the required symbol in the compiled MIB Python files or behaviour JSON. This may be due to incomplete MIB compilation or missing columns in the behaviour JSON.

**Solution:**
- Ensure all required MIBs are compiled and available in the `compiled-mibs/` directory.
- Verify the behaviour JSON files contain all necessary symbols for table registration.

### Value Model Incompatibility Warnings
```
WARNING app.agent [MainThread] Could not register table ifTestTable: Failed columns: ifTestType: AutonomousType -> ObjectIdentifier (base type supported but value model incompatible: WrongValueError(...)); ifTestOwner: OwnerString -> OctetString (base type supported but value model incompatible: WrongValueError(...))
WARNING app.agent [MainThread] Could not register table hrStorageTable: Failed columns: hrStorageType: AutonomousType -> ObjectIdentifier (base type supported but value model incompatible: WrongValueError(...))
WARNING app.agent [MainThread] Could not register table hrDeviceTable: Failed columns: hrDeviceType: AutonomousType -> ObjectIdentifier (base type supported but value model incompatible: WrongValueError(...))
```
**Cause:**
- The agent attempted to instantiate a value for a column, but the default value or type mapping was incompatible with the expected SNMP type. This is often due to incorrect defaults in the behaviour JSON or missing type conversion logic.

**Solution:**
- Update the behaviour generator to use valid SNMP defaults for types like `OctetString` and `ObjectIdentifier`.
- Ensure type mapping logic in the agent and generator matches SNMP expectations.

---

## 3. Deprecation Warnings

### Example
```
DeprecationWarning: importSymbols is deprecated. Please use import_symbols instead.
```
**Cause:**
- The code or compiled MIBs use deprecated PySNMP APIs.

**Solution:**
- Update MIB compilation scripts and code to use the latest PySNMP API methods (e.g., `import_symbols` instead of `importSymbols`).

---

## 4. General Recommendations
- Always run tests after updating MIBs or behaviour JSON files.
- If you see missing symbol warnings, check both the compiled MIBs and the behaviour JSON for completeness.
- For import errors, verify your working directory and Python path.
- For value model errors, review type mapping and default value logic in your generator and agent code.

---

_Last updated: 2026-01-22_
