# SNMP Tools - Wrapper Scripts

This folder contains SnmpSoft SNMP tools and convenient wrapper scripts with preconfigured defaults for testing the local SNMP agent.

## Tools Included

- **SnmpGet.exe** - SNMP GET operations
- **SnmpWalk.exe** - SNMP WALK operations  
- **SnmpSet.exe** - SNMP SET operations
- **SnmpTrapGen.exe** - SNMP TRAP generation

## Wrapper Scripts

### Batch Files (Easy Command Line)

#### snmpget.bat
Get a single OID value.

```batch
snmpget.bat <OID> [host:port] [community]
```

**Examples:**
```batch
snmpget.bat .1.3.6.1.2.1.1.1.0
snmpget.bat sysDescr.0
snmpget.bat .1.3.6.1.4.1.99999.1.1.0
snmpget.bat .1.3.6.1.2.1.1.1.0 192.168.1.100:161 private
```

**Defaults:**
- Host: `127.0.0.1:11161`
- Community: `public`
- Version: `v2c`

---

#### snmpwalk.bat
Walk an OID tree.

```batch
snmpwalk.bat [OID] [host:port] [community]
```

**Examples:**
```batch
snmpwalk.bat
snmpwalk.bat .1.3.6.1.2.1.1
snmpwalk.bat .1.3.6.1.4.1.99999
snmpwalk.bat system 192.168.1.100:161 private
```

**Defaults:**
- OID: `.1` (entire tree)
- Host: `127.0.0.1:11161`
- Community: `public`
- Version: `v2c`

---

#### snmpset.bat
Set an OID value.

```batch
snmpset.bat <OID> <type> <value> [host:port] [community]
```

**Types:**
- `i` - Integer
- `s` - String
- `x` - Hex string
- `d` - Decimal string
- `a` - IP Address
- `o` - OID
- `t` - TimeTicks

**Examples:**
```batch
snmpset.bat .1.3.6.1.2.1.1.1.0 s "My System Description"
snmpset.bat .1.3.6.1.4.1.99999.1.1.0 s "Hello World"
snmpset.bat .1.3.6.1.4.1.99999.1.2.0 i 42
```

**Defaults:**
- Host: `127.0.0.1:11161`
- Community: `public`
- Version: `v2c`

---

### PowerShell Scripts (Advanced)

#### snmpget.ps1
```powershell
.\snmpget.ps1 -OID <oid> [-Host <host:port>] [-Community <community>] [-Version <v1|v2c|v3>]
```

**Examples:**
```powershell
.\snmpget.ps1 .1.3.6.1.2.1.1.1.0
.\snmpget.ps1 -OID sysDescr.0
.\snmpget.ps1 -OID .1.3.6.1.4.1.99999.1.1.0 -Host 192.168.1.100:161
```

#### snmpwalk.ps1
```powershell
.\snmpwalk.ps1 [-OID <oid>] [-Host <host:port>] [-Community <community>] [-Version <v1|v2c|v3>]
```

**Examples:**
```powershell
.\snmpwalk.ps1
.\snmpwalk.ps1 -OID .1.3.6.1.2.1.1
.\snmpwalk.ps1 -OID .1.3.6.1.4.1.99999
```

#### snmpset.ps1
```powershell
.\snmpset.ps1 -OID <oid> -Type <type> -Value <value> [-Host <host:port>] [-Community <community>]
```

**Examples:**
```powershell
.\snmpset.ps1 -OID .1.3.6.1.2.1.1.1.0 -Type s -Value "My System"
.\snmpset.ps1 .1.3.6.1.4.1.99999.1.2.0 i 42
```

---

### Quick Reference Scripts

Convenient one-click scripts for common operations:

- **get-sysdescr.bat** - Get system description
- **walk-system.bat** - Walk the system group (.1.3.6.1.2.1.1)
- **walk-enterprise.bat** - Walk the enterprise MIB (.1.3.6.1.4.1.99999)

---

## Common OIDs

### SNMPv2-MIB System Group
```
.1.3.6.1.2.1.1.1.0  - sysDescr (System Description)
.1.3.6.1.2.1.1.2.0  - sysObjectID
.1.3.6.1.2.1.1.3.0  - sysUpTime
.1.3.6.1.2.1.1.4.0  - sysContact
.1.3.6.1.2.1.1.5.0  - sysName
.1.3.6.1.2.1.1.6.0  - sysLocation
```

### Enterprise MIB (99999)
```
.1.3.6.1.4.1.99999.1.1.0  - myString
.1.3.6.1.4.1.99999.1.2.0  - myCounter
.1.3.6.1.4.1.99999.1.3.0  - myGauge
.1.3.6.1.4.1.99999.2      - myTable
```

---

## Usage Tips

1. **Add bin folder to PATH** for easier access:
   ```powershell
   $env:PATH += ";C:\code\devspace\snmpmore\bin"
   ```

2. **Make sure the agent is running** on port 11161:
   ```bash
   python run_agent_with_rest.py
   ```

3. **Test connectivity**:
   ```batch
   get-sysdescr.bat
   ```

4. **Explore the MIB**:
   ```batch
   walk-system.bat
   walk-enterprise.bat
   ```

---

## Troubleshooting

**"No response from agent"**
- Check that the SNMP agent is running
- Verify the port (default: 11161)
- Check firewall settings

**"Access denied"**
- Verify the community string (default: public)
- Check VACM configuration in the agent

**"OID not found"**
- Use snmpwalk to explore available OIDs
- Check that the MIB objects are registered in the agent

