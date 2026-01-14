#!/usr/bin/env python3
"""
AgentX subagent example (Net-SNMP via netsnmpagent).

What we changed / discovered while getting this working on Ubuntu/Debian:

1) AgentX is a client-server setup:
   - snmpd is the AgentX master (server) and must be running first.
   - this script is the subagent (client) and connects to the master socket.

   Net-SNMP defaults the AgentX master socket to /var/agentx/master on Unix-like
   systems, but distros can vary. snmpd can also be configured with agentXSocket.
   See snmpd docs for the default and the agentXSocket option.  [oai_citation:0‡Net-SNMP](https://www.net-snmp.org/docs/man/snmpd.html?utm_source=chatgpt.com)

2) Permissions on the AgentX socket:
   - On your box /var/agentx was root:root and the socket existed but your user
     could not connect reliably.
   - Fix was to make snmpd create the socket as Debian-snmp:Debian-snmp with
     restrictive perms (0660 on the socket, 0770 on the directory), then add
     your user to that group.

   Example snmpd.conf lines (near "master agentx"):
     master agentx
     agentXSocket /var/agentx/master
     agentXPerms 0660 0770 Debian-snmp Debian-snmp

3) VACM view / access:
   - Your "public" community was initially bound to a system-only view, so
     enterprise OIDs (.1.3.6.1.4.1...) were blocked.
   - Fix was to bind the community to a view that includes your enterprise subtree.

4) Persistent file error:
   - Net-SNMP libraries try to write a per-application persistent config file.
     You saw:
       read_config_store open failure on /var/lib/snmp/MyEnterpriseAgent.conf
   - Fix is to set SNMP_PERSISTENT_FILE to a path your user can write to.  [oai_citation:1‡SourceForge](https://sourceforge.net/p/net-snmp/mailman/message/16144431/?utm_source=chatgpt.com)

Fedora/RHEL notes:
- The AgentX default is still commonly /var/agentx/master, but permissions and
  SELinux can get in the way.
- There are known cases where agentXPerms chmod/chown can be blocked by SELinux
  policy. If you hit that, you may need SELinux adjustments or use a TCP AgentX
  socket bound to localhost instead.  [oai_citation:2‡Red Hat Bugzilla](https://bugzilla.redhat.com/show_bug.cgi?id=978864&utm_source=chatgpt.com)

Enterprise numbers are assigned by IANA. For testing we use 99999.
In production, apply for your own PEN.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import netsnmpagent


ENTERPRISE_OID = ".1.3.6.1.4.1.99999"


def _default_persistent_file(agent_name: str) -> str:
    """
    Choose a user-writable persistent file path.

    This avoids:
      read_config_store open failure on /var/lib/snmp/<AgentName>.conf

    We set SNMP_PERSISTENT_FILE for *this process only*.
    """
    snmp_dir = Path.home() / ".snmp"
    snmp_dir.mkdir(parents=True, exist_ok=True)
    return str(snmp_dir / f"{agent_name}.conf")


def _make_agent() -> netsnmpagent.netsnmpAgent:
    """
    Create the AgentX subagent.

    MasterSocket must match the snmpd AgentX socket path.
    Default for Net-SNMP is commonly /var/agentx/master.  [oai_citation:3‡Net-SNMP](https://www.net-snmp.org/docs/man/snmpd.html?utm_source=chatgpt.com)
    """
    agent_name = "MyEnterpriseAgent"

    # If SNMP_PERSISTENT_FILE is not set, Net-SNMP may try to write under /var/lib/snmp
    # and fail for non-root users. Setting this fixes the warning.  [oai_citation:4‡SourceForge](https://sourceforge.net/p/net-snmp/mailman/message/16144431/?utm_source=chatgpt.com)
    os.environ.setdefault("SNMP_PERSISTENT_FILE", _default_persistent_file(agent_name))

    # Allow override without editing code:
    # - useful across distros (some use /run/snmp/agentx/master or similar)
    master_socket = os.environ.get("AGENTX_MASTER_SOCKET", "/var/agentx/master")

    return netsnmpagent.netsnmpAgent(
        AgentName=agent_name,
        MasterSocket=master_socket,
    )


agent = _make_agent()

# ============================================================================
# SCALAR OBJECTS
# ============================================================================
# Scalars represent single values. In SNMP, scalar instances always end in .0
# OID pattern: .1.3.6.1.4.1.99999.1.X.0
#
# Query with: snmpget -v2c -c public localhost .1.3.6.1.4.1.99999.1.X.0
# Walk all scalars: snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999.1

my_string = agent.OctetString(
    oidstr=f"{ENTERPRISE_OID}.1.1.0",  # .1.3.6.1.4.1.99999.1.1.0
    initval="Hello from AgentX",
    writable=True,
)

my_counter = agent.Integer32(
    oidstr=f"{ENTERPRISE_OID}.1.2.0",  # .1.3.6.1.4.1.99999.1.2.0
    initval=0,
    writable=False,
)

my_gauge = agent.Unsigned32(
    oidstr=f"{ENTERPRISE_OID}.1.3.0",  # .1.3.6.1.4.1.99999.1.3.0
    initval=42,
    writable=False,
)

# ============================================================================
# TABLE OBJECT
# ============================================================================
# Tables represent multiple rows of structured data.
# OID pattern: .1.3.6.1.4.1.99999.2.1.COLUMN.ROW
#
# Structure:
#   .1.3.6.1.4.1.99999.2       = table base
#   .1.3.6.1.4.1.99999.2.0     = row count (counterobj)
#   .1.3.6.1.4.1.99999.2.1     = table entry
#   .1.3.6.1.4.1.99999.2.1.1.X = column 1 (index) for row X
#   .1.3.6.1.4.1.99999.2.1.2.X = column 2 (sensor name) for row X
#   .1.3.6.1.4.1.99999.2.1.3.X = column 3 (sensor value) for row X
#   .1.3.6.1.4.1.99999.2.1.4.X = column 4 (sensor status) for row X
#
# Query with:
#   snmpwalk -v2c -c public localhost .1.3.6.1.4.1.99999.2
#   snmptable -v2c -c public localhost .1.3.6.1.4.1.99999.2

my_table = agent.Table(
    oidstr=f"{ENTERPRISE_OID}.2",
    indexes=[agent.Integer32()],  # Column 1: index (implicit)
    columns=[
        (2, agent.OctetString()),  # Column 2: sensor name
        (3, agent.Integer32()),    # Column 3: sensor value
        (4, agent.OctetString()),  # Column 4: sensor status
    ],
    counterobj=agent.Unsigned32(
        oidstr=f"{ENTERPRISE_OID}.2.0",  # Row count at .1.3.6.1.4.1.99999.2.0.0
        initval=0,
    ),
)


def populate_table() -> None:
    """
    Populate the example table with a few rows.

    Each row has:
      - Index (column 1, implicit): unique row identifier
      - Name (column 2): sensor name string
      - Value (column 3): sensor reading integer
      - Status (column 4): sensor status string
    """
    my_table.clear()

    # Example data: (index, name, value, status)
    data = [
        (1, "sensor_a", 25, "ok"),
        (2, "sensor_b", 30, "ok"),
        (3, "sensor_c", 45, "warning"),
    ]

    for idx, name, value, status in data:
        row = my_table.addRow([agent.Integer32(idx)])
        row.setRowCell(2, agent.OctetString(name))    # Column 2: name
        row.setRowCell(3, agent.Integer32(value))     # Column 3: value
        row.setRowCell(4, agent.OctetString(status))  # Column 4: status


def update_values() -> None:
    """Update dynamic values periodically."""
    my_counter.update(my_counter.value() + 1)
    # my_gauge.update(...)  # hook your real metric here
    populate_table()


def shutdown_handler(signum: int, frame) -> None:
    """Clean shutdown on SIGTERM/SIGINT."""
    _ = (signum, frame)
    print("\nShutting down...")
    agent.shutdown()
    raise SystemExit(0)


def start_with_retries(max_attempts: int = 30, delay_s: float = 1.0) -> None:
    """
    Try to connect to the AgentX master a few times.

    This makes startup robust if you restart snmpd and then immediately start
    the subagent.
    """
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            agent.start()
            return
        except netsnmpagent.netsnmpAgentException as exc:
            last_err = exc
            print(f"[Warn] AgentX connect attempt {attempt}/{max_attempts} failed: {exc}")
            time.sleep(delay_s)

    raise SystemExit(f"Failed to connect to snmpd via AgentX after {max_attempts} attempts: {last_err}")


def main() -> None:
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    populate_table()

    # Important: start snmpd first, then start this subagent.
    # If snmpd restarts later, this subagent will typically need restarting too.
    start_with_retries()

    print(f"AgentX subagent running, registered under {ENTERPRISE_OID}")
    print(f"Using AgentX socket: {os.environ.get('AGENTX_MASTER_SOCKET', '/var/agentx/master')}")
    print(f"Persistent file: {os.environ.get('SNMP_PERSISTENT_FILE')}")
    print("Press Ctrl+C to stop")

    # Process requests; update values periodically.
    next_update = time.monotonic() + 5.0
    while True:
        agent.check_and_process()
        time.sleep(0.05)  # avoid busy-looping

        now = time.monotonic()
        if now >= next_update:
            update_values()
            next_update = now + 5.0


if __name__ == "__main__":
    main()