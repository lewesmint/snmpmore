# SNMP AgentX Subagent Demo

A demonstration of implementing a custom enterprise MIB using SNMP AgentX protocol with Python and Net-SNMP.

## What This Demonstrates

This project shows how to:
- Create an SNMP subagent that extends the standard `snmpd` daemon
- Register custom enterprise OIDs (scalars and tables)
- Handle common AgentX deployment challenges (permissions, views, persistence)
- Build a production-ready subagent with retry logic and graceful shutdown

## Architecture

**AgentX** is a protocol that allows multiple agents to serve different parts of the MIB tree:
- **Master Agent** (`snmpd`) - handles SNMP requests from the network
- **Subagent** (`my-agentx.py`) - registers custom OIDs and responds to queries for them

The subagent in this demo registers under `.1.3.6.1.4.1.99999` (a test enterprise number) and exposes:
- **Scalars**: A string, counter, and gauge
- **Table**: Sensor data with name, value, and status columns

## Prerequisites

### System Packages
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install snmpd snmp libsnmp-dev

# Fedora/RHEL
sudo dnf install net-snmp net-snmp-utils net-snmp-devel
```

### Python Dependencies
```bash
pip install netsnmpagent
```

Or if using system Python:
```bash
# Ubuntu/Debian
sudo apt-get install python3-netsnmpagent

# Or via pip
pip3 install --user netsnmpagent
```

## Quick Start

### 1. Configure snmpd

Copy the provided configuration to your system:
```bash
sudo cp data/snmpd.conf /etc/snmp/snmpd.conf
```

**Key configuration points** (already set in `data/snmpd.conf`):
- Enables AgentX master mode
- Sets AgentX socket to `/var/agentx/master`
- Configures permissions for `Debian-snmp` group
- Creates a view that includes the enterprise subtree `.1.3.6.1.4.1.99999`
- Binds the `public` community to this view

### 2. Fix Permissions

Add your user to the SNMP group so the subagent can connect:
```bash
# Ubuntu/Debian
sudo usermod -a -G Debian-snmp $USER

# Fedora/RHEL
sudo usermod -a -G snmp $USER
```

**Important**: Log out and back in (or run `newgrp Debian-snmp` or `newgrp snmp`) for group membership to take effect.

**For Fedora/RHEL**: You'll also need to update the `agentXPerms` line in `/etc/snmp/snmpd.conf`:
```bash
# Change this line:
agentXPerms 0660 0770 Debian-snmp Debian-snmp

# To this:
agentXPerms 0660 0770 snmp snmp
```

### 3. Start snmpd

```bash
sudo systemctl restart snmpd
sudo systemctl status snmpd
```

Verify the AgentX socket exists:
```bash
ls -la /var/agentx/master
# Should show: srw-rw---- 1 Debian-snmp Debian-snmp ... /var/agentx/master
```

### 4. Run the Subagent

```bash
./my-agentx.py
```

You should see:
```
AgentX subagent running, registered under .1.3.6.1.4.1.99999
Using AgentX socket: /var/agentx/master
Persistent file: /home/youruser/.snmp/MyEnterpriseAgent.conf
Press Ctrl+C to stop
```

### 5. Test It

In another terminal, query your custom MIB:
```bash
# Walk the entire enterprise subtree
snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999
```

Expected output:
```
iso.3.6.1.4.1.99999.1.1.0 = STRING: "Hello from AgentX"      # Scalar: my_string
iso.3.6.1.4.1.99999.1.2.0 = INTEGER: 5                       # Scalar: my_counter (increments every 5s)
iso.3.6.1.4.1.99999.1.3.0 = Gauge32: 42                      # Scalar: my_gauge
iso.3.6.1.4.1.99999.2.0.0 = Gauge32: 3                       # Table: row count
iso.3.6.1.4.1.99999.2.1.1.1 = INTEGER: 1                     # Table: row 1, index
iso.3.6.1.4.1.99999.2.1.2.1 = STRING: "sensor_a"             # Table: row 1, column 2 (name)
iso.3.6.1.4.1.99999.2.1.3.1 = INTEGER: 25                    # Table: row 1, column 3 (value)
iso.3.6.1.4.1.99999.2.1.4.1 = STRING: "ok"                   # Table: row 1, column 4 (status)
iso.3.6.1.4.1.99999.2.1.1.2 = INTEGER: 2                     # Table: row 2, index
iso.3.6.1.4.1.99999.2.1.2.2 = STRING: "sensor_b"             # Table: row 2, column 2 (name)
iso.3.6.1.4.1.99999.2.1.3.2 = INTEGER: 30                    # Table: row 2, column 3 (value)
iso.3.6.1.4.1.99999.2.1.4.2 = STRING: "ok"                   # Table: row 2, column 4 (status)
iso.3.6.1.4.1.99999.2.1.1.3 = INTEGER: 3                     # Table: row 3, index
iso.3.6.1.4.1.99999.2.1.2.3 = STRING: "sensor_c"             # Table: row 3, column 2 (name)
iso.3.6.1.4.1.99999.2.1.3.3 = INTEGER: 45                    # Table: row 3, column 3 (value)
iso.3.6.1.4.1.99999.2.1.4.3 = STRING: "warning"              # Table: row 3, column 4 (status)
```

#### Interpreting the Output

When you run `snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999`, you'll see output like:

```
SNMPv2-SMI::enterprises.99999.1.1.0.0 = STRING: "Hello from AgentX"
SNMPv2-SMI::enterprises.99999.1.2.0.0 = INTEGER: 1
SNMPv2-SMI::enterprises.99999.1.3.0.0 = Gauge32: 42
SNMPv2-SMI::enterprises.99999.2.0.0 = Gauge32: 3
SNMPv2-SMI::enterprises.99999.2.1.2.1 = STRING: "sensor_a"
SNMPv2-SMI::enterprises.99999.2.1.2.2 = STRING: "sensor_b"
SNMPv2-SMI::enterprises.99999.2.1.2.3 = STRING: "sensor_c"
SNMPv2-SMI::enterprises.99999.2.1.3.1 = INTEGER: 25
SNMPv2-SMI::enterprises.99999.2.1.3.2 = INTEGER: 30
SNMPv2-SMI::enterprises.99999.2.1.3.3 = INTEGER: 45
SNMPv2-SMI::enterprises.99999.2.1.4.1 = STRING: "ok"
SNMPv2-SMI::enterprises.99999.2.1.4.2 = STRING: "ok"
SNMPv2-SMI::enterprises.99999.2.1.4.3 = STRING: "warning"
```

**How to read this:**

| OID | Type | What It Is |
|-----|------|------------|
| `enterprises.99999.1.1.0.0` | **Scalar** | my_string - a writable string value |
| `enterprises.99999.1.2.0.0` | **Scalar** | my_counter - increments every 5 seconds |
| `enterprises.99999.1.3.0.0` | **Scalar** | my_gauge - a gauge value (currently 42) |
| `enterprises.99999.2.0.0` | **Table metadata** | Row count (3 rows in the table) |
| `enterprises.99999.2.1.2.1` | **Table cell** | Row 1, Column 2 (name): "sensor_a" |
| `enterprises.99999.2.1.2.2` | **Table cell** | Row 2, Column 2 (name): "sensor_b" |
| `enterprises.99999.2.1.2.3` | **Table cell** | Row 3, Column 2 (name): "sensor_c" |
| `enterprises.99999.2.1.3.1` | **Table cell** | Row 1, Column 3 (value): 25 |
| `enterprises.99999.2.1.3.2` | **Table cell** | Row 2, Column 3 (value): 30 |
| `enterprises.99999.2.1.3.3` | **Table cell** | Row 3, Column 3 (value): 45 |
| `enterprises.99999.2.1.4.1` | **Table cell** | Row 1, Column 4 (status): "ok" |
| `enterprises.99999.2.1.4.2` | **Table cell** | Row 2, Column 4 (status): "ok" |
| `enterprises.99999.2.1.4.3` | **Table cell** | Row 3, Column 4 (status): "warning" |

**Pattern recognition:**
- **Scalars**: `enterprises.99999.1.X.0.0` - single values, always end in `.0.0`
- **Table cells**: `enterprises.99999.2.1.COLUMN.ROW` - organized by column, then row
  - Column 2 = sensor names (all listed together)
  - Column 3 = sensor values (all listed together)
  - Column 4 = sensor statuses (all listed together)

#### Understanding the OID Structure

**Scalars** (end in `.0.0` in the output):
```bash
# Get individual scalar values
snmpget -v2c -c public localhost .1.3.6.1.4.1.99999.1.1.0  # my_string
snmpget -v2c -c public localhost .1.3.6.1.4.1.99999.1.2.0  # my_counter
snmpget -v2c -c public localhost .1.3.6.1.4.1.99999.1.3.0  # my_gauge

# Walk all scalars
snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999.1
```

**Table** (OID pattern: `enterprises.99999.2.1.COLUMN.ROW`):
```bash
# Walk the entire table
snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999.2

# Get a specific cell (row 1, column 2 = sensor_a name)
snmpget -v2c -c public localhost .1.3.6.1.4.1.99999.2.1.2.1

# Walk a specific column (all sensor names - column 2)
snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999.2.1.2
```

**Pro tip**: Use `snmptable` for a much nicer tabular view:
```bash
snmptable -v2c -c public localhost .1.3.6.1.4.1.99999.2
```

Output:
```
SNMP table: SNMPv2-SMI::enterprises.99999.2.1

 SNMP table SNMPv2-SMI::enterprises.99999.2.1.2 SNMPv2-SMI::enterprises.99999.2.1.3 SNMPv2-SMI::enterprises.99999.2.1.4
        ? sensor_a                                                              25 ok
        ? sensor_b                                                              30 ok
        ? sensor_c                                                              45 warning
```

This shows the table structure much more clearly:
- Each row is a sensor
- Column 2 = sensor name
- Column 3 = sensor value
- Column 4 = sensor status

## Troubleshooting

### "Failed to connect to snmpd via AgentX"

**Cause**: `snmpd` is not running or the socket path is wrong.

**Fix**:
```bash
sudo systemctl status snmpd
ls -la /var/agentx/master
```

### "Permission denied" on AgentX socket

**Cause**: Your user is not in the SNMP group, or SELinux is blocking access.

**Fix**:
```bash
# Check group membership
groups  # Should list Debian-snmp (Ubuntu) or snmp (Fedora/RHEL)

# Ubuntu/Debian
sudo usermod -a -G Debian-snmp $USER

# Fedora/RHEL
sudo usermod -a -G snmp $USER

# Log out and back in, or:
newgrp Debian-snmp  # or newgrp snmp
```

**For Fedora/RHEL with SELinux**: Check for SELinux denials and see Platform Notes section.

### snmpwalk returns nothing for .1.3.6.1.4.1.99999

**Cause**: The SNMP view doesn't include your enterprise OID.

**Fix**: Ensure `/etc/snmp/snmpd.conf` has:
```
view   systemplusagentx  included   .1.3.6.1.4.1.99999
rocommunity  public default -V systemplusagentx
```

### "read_config_store open failure on /var/lib/snmp/..."

**Cause**: Net-SNMP tries to write persistent state to a root-owned directory.

**Fix**: The script automatically handles this by setting `SNMP_PERSISTENT_FILE` to `~/.snmp/MyEnterpriseAgent.conf`. If you still see this, set it manually:
```bash
export SNMP_PERSISTENT_FILE=~/.snmp/MyEnterpriseAgent.conf
./my-agentx.py
```

## Customization

### Change the Enterprise Number

Edit `my-agentx.py`:
```python
ENTERPRISE_OID = ".1.3.6.1.4.1.YOUR_PEN_HERE"
```

And update `data/snmpd.conf`:
```
view   systemplusagentx  included   .1.3.6.1.4.1.YOUR_PEN_HERE
```

**Note**: Enterprise number 99999 is for testing only. For production, obtain your own Private Enterprise Number (PEN) from [IANA](https://www.iana.org/assignments/enterprise-numbers/).

### Add Your Own Metrics

See the examples in `my-agentx.py`:
- **Scalars**: `agent.OctetString()`, `agent.Integer32()`, `agent.Unsigned32()`
- **Tables**: `agent.Table()` with rows and columns
- **Update logic**: Modify `update_values()` to pull real data from your system

## Platform Notes

### Ubuntu/Debian
- Default AgentX socket: `/var/agentx/master`
- SNMP user/group: `Debian-snmp`
- Works out of the box with provided config

### Fedora/RHEL - Important Differences

**1. User/Group Name**
- SNMP user/group is `snmp` (not `Debian-snmp`)
- Update `agentXPerms` in `/etc/snmp/snmpd.conf`:
  ```
  agentXPerms 0660 0770 snmp snmp
  ```
- Add your user to the `snmp` group:
  ```bash
  sudo usermod -a -G snmp $USER
  newgrp snmp
  ```

**2. SELinux Considerations**
- SELinux may block `agentXPerms` from changing socket ownership/permissions
- Check for denials: `sudo ausearch -m avc -ts recent | grep agentx`
- **Option A - Allow via SELinux policy** (recommended):
  ```bash
  # Check for denials
  sudo ausearch -m avc -ts recent | grep snmp
  # Generate and apply policy if needed
  sudo ausearch -m avc -ts recent | audit2allow -M snmp_agentx
  sudo semodule -i snmp_agentx.pp
  ```
- **Option B - Use TCP socket instead** (workaround):
  ```
  # In /etc/snmp/snmpd.conf, replace:
  agentXSocket /var/agentx/master
  agentXPerms 0660 0770 snmp snmp

  # With:
  agentXSocket tcp:localhost:705
  ```
  Then set environment variable before running the subagent:
  ```bash
  export AGENTX_MASTER_SOCKET=tcp:localhost:705
  ./my-agentx.py
  ```

**3. Firewall**
- If accessing SNMP remotely, open the firewall:
  ```bash
  sudo firewall-cmd --permanent --add-service=snmp
  sudo firewall-cmd --reload
  ```

**4. Socket Directory**
- Ensure `/var/agentx` directory exists and has correct permissions:
  ```bash
  sudo mkdir -p /var/agentx
  sudo chown snmp:snmp /var/agentx
  sudo chmod 0770 /var/agentx
  ```

## Production Deployment

For production use, consider:
1. **Systemd service**: Create a service unit to auto-start the subagent
2. **Monitoring**: Ensure the subagent restarts if it crashes
3. **Security**: Use SNMPv3 with authentication and encryption (see `data/snmpd.conf`)
4. **Network access**: Restrict SNMP access to monitoring systems only
5. **Real PEN**: Register your own enterprise number with IANA

## References

- [Net-SNMP AgentX Documentation](https://www.net-snmp.org/docs/man/snmpd.html)
- [netsnmpagent Python Library](https://pypi.org/project/netsnmpagent/)
- [IANA Private Enterprise Numbers](https://www.iana.org/assignments/enterprise-numbers/)
- [RFC 2741 - Agent Extensibility (AgentX) Protocol](https://www.rfc-editor.org/rfc/rfc2741)

## License

This is a demonstration project. Use freely for learning and as a starting point for your own implementations.

