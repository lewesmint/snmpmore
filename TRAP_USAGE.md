# SNMP Trap Usage Guide

This guide explains how to send SNMP traps using the pysnmp library.

## Overview

SNMP traps are asynchronous notifications sent from an SNMP agent to a management station (trap receiver) to alert about specific events or conditions.

## Quick Start

### Sending Traps

Run the demo script to send test traps:

```bash
python simple_trap_demo.py
```

This will send 6 different traps demonstrating various SNMP data types:
1. **OctetString** - Text message
2. **Integer** - Numeric value
3. **Counter32** - 32-bit counter
4. **Gauge32** - Gauge value (can go up/down)
5. **IpAddress** - IP address
6. **TimeTicks** - Time value

### Monitoring Traps

#### Option 1: Using tcpdump

```bash
sudo tcpdump -i lo -n port 1162 -vv
```

Then in another terminal:
```bash
python simple_trap_demo.py
```

#### Option 2: Using snmptrapd

Create a config file `snmptrapd.conf`:
```
authCommunity log,execute,net public
```

Run snmptrapd (requires root for port 162):
```bash
sudo snmptrapd -f -Lo -c snmptrapd.conf
```

For non-root, use port 1162:
```bash
snmptrapd -f -Lo -c snmptrapd.conf -p 1162
```

## Code Examples

### Basic Trap Sending

```python
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntforg
from pysnmp.proto.api import v2c

# Create SNMP engine
snmpEngine = engine.SnmpEngine()

# Setup transport
config.add_transport(
    snmpEngine,
    udp.DOMAIN_NAME,
    udp.UdpTransport().open_client_mode()
)

# Setup community
config.add_v1_system(snmpEngine, 'my-area', 'public')

# Setup notification target
config.add_target_parameters(snmpEngine, 'my-creds', 'my-area', 'noAuthNoPriv', 1)
config.add_target_address(
    snmpEngine, 'my-nms',
    udp.DOMAIN_NAME, ('127.0.0.1', 1162),
    'my-creds',
    tagList='all-my-managers'
)

# Setup notification
config.add_notification_target(
    snmpEngine, 'test-notification', 'my-filter', 'all-my-managers', 'trap'
)

# Create notification originator
ntfOrg = ntforg.NotificationOriginator()

# Send a trap
ntfOrg.send_varbinds(
    snmpEngine,
    'test-notification',
    None, '',  # contextEngineId, contextName
    [
        # snmpTrapOID
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        # Custom variable binding
        ((1, 3, 6, 1, 4, 1, 99999, 1, 0), v2c.OctetString('Alert message'))
    ]
)

# Cleanup
snmpEngine.transport_dispatcher.close_dispatcher()
```

### Sending Different Data Types

```python
# String
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 1, 0), v2c.OctetString('Alert: High temperature'))
])

# Integer
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 2, 0), v2c.Integer(999))
])

# Counter32
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 5, 0), v2c.Counter32(54321))
])

# Gauge32
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 6, 0), v2c.Gauge32(95))
])

# IpAddress
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 8, 0), v2c.IpAddress('10.0.0.1'))
])

# TimeTicks
ntfOrg.send_varbinds(snmpEngine, 'test-notification', None, '', [
    ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
    ((1, 3, 6, 1, 4, 1, 99999, 7, 0), v2c.TimeTicks(12345))
])
```

## Files

- **simple_trap_demo.py** - Complete working example of sending traps
- **trap_sender.py** - TrapSender class for MIB-based trap sending
- **my-pysnmp-agent.py** - SNMP agent with trap sending capability

## Notes

- Standard SNMP trap port is **162** (requires root/sudo)
- For testing without root, use port **1162** or higher
- Traps are "fire and forget" - no acknowledgment
- For reliable delivery, use **inform** instead of **trap**

