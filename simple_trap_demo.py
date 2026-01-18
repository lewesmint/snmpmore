#!/usr/bin/env python3
"""
Simple SNMP trap demonstration using pysnmp v7.
Shows how to send traps with different data types.
"""

from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntforg
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from pysnmp.proto.api import v2c

def send_trap_demo() -> None:
    """Send a simple SNMP trap."""
    
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
        snmpEngine,
        'my-nms',
        udp.DOMAIN_NAME, ('127.0.0.1', 1162),
        'my-creds',
        timeout=1,
        retryCount=5,
        tagList=b'all-my-managers',  # Correct: bytes literal
        sourceAddress=None,
    )
    
    # Setup notification
    config.add_notification_target(
        snmpEngine, 'test-notification', 'my-filter', 'all-my-managers', 'trap'
    )
    
    # Create notification originator
    ntfOrg = ntforg.NotificationOriginator()
    
    print("=" * 70)
    print("SNMP Trap Sender - Simple Demo")
    print("=" * 70)
    print("Sending traps to localhost:1162")
    print()
    
    # Send trap 1: String value
    print("Sending trap 1: String value...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 1, 0), v2c.OctetString('Alert: Test trap message'))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',  # contextEngineId, contextName
        object_types
    )
    print("✓ Sent")

    # Send trap 2: Integer value
    print("\nSending trap 2: Integer value...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 2, 0), v2c.Integer(999))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',
        object_types
    )
    print("✓ Sent")

    # Send trap 3: Counter32
    print("\nSending trap 3: Counter32...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 5, 0), v2c.Counter32(54321))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',
        object_types
    )
    print("✓ Sent")

    # Send trap 4: Gauge32
    print("\nSending trap 4: Gauge32 (high value alert)...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 6, 0), v2c.Gauge32(95))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',
        object_types
    )
    print("✓ Sent")

    # Send trap 5: IpAddress
    print("\nSending trap 5: IpAddress...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 8, 0), v2c.IpAddress('10.0.0.1'))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',
        object_types
    )
    print("✓ Sent")

    # Send trap 6: TimeTicks
    print("\nSending trap 6: TimeTicks...")
    varBinds = [
        ((1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0), v2c.ObjectIdentifier((1, 3, 6, 1, 4, 1, 99999))),
        ((1, 3, 6, 1, 4, 1, 99999, 7, 0), v2c.TimeTicks(12345))
    ]
    object_types = tuple(
        ObjectType(ObjectIdentity(*oid), value)
        for oid, value in varBinds
    )
    ntfOrg.send_varbinds(
        snmpEngine,
        'test-notification',
        None, '',
        object_types
    )
    print("✓ Sent")
    
    print("\n" + "=" * 70)
    print("All traps sent!")
    print("=" * 70)
    print()
    print("To receive these traps, you can use:")
    print("  sudo tcpdump -i lo -n port 1162 -vv")
    print()
    print("Or run snmptrapd (requires root for port 162):")
    print("  sudo snmptrapd -f -Lo")
    print("=" * 70)
    
    # Cleanup
    snmpEngine.transport_dispatcher.close_dispatcher()


if __name__ == '__main__':
    send_trap_demo()

