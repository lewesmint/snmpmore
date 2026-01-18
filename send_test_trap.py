#!/usr/bin/env python3
"""
Simple script to send test SNMP traps.
This demonstrates how to send traps using pysnmp v7.
"""

import asyncio
import logging
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, NotificationType,
    send_notification
)
from pysnmp.smi.rfc1902 import ObjectIdentity
from pysnmp.proto.api import v2c
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def send_trap(
    trap_dest: tuple[str, int],
    oid: tuple[int, ...],
    value: Any,
    trap_type: str = 'trap'
) -> None:
    """Send an SNMP trap or inform.

    Args:
        trap_dest: Tuple of (host, port) for trap receiver
        oid: OID tuple for the variable binding
        value: Value to send
        trap_type: 'trap' or 'inform'
    """
    try:
        oid_str = '.'.join(map(str, oid))
        logger.info(f"Sending {trap_type} to {trap_dest[0]}:{trap_dest[1]}")
        logger.info(f"  OID: {oid_str}")
        logger.info(f"  Value: {value}")

        # Send the notification with variable binding
        notification = NotificationType(ObjectIdentity(oid_str)).add_var_binds((oid_str, value))

        result = await send_notification(
            SnmpEngine(),
            CommunityData('public'),
            await UdpTransportTarget.create(trap_dest),
            ContextData(),
            trap_type,
            notification
        )

        errorIndication = result[0]
        if errorIndication:
            logger.error(f'Trap send error: {errorIndication}')
        else:
            logger.info(f'✓ Trap sent successfully!')

    except Exception as e:
        logger.error(f'Exception sending trap: {e}')
        import traceback
        traceback.print_exc()


async def main() -> None:
    """Send various test traps."""
    # Trap destination (using port 1162 to avoid needing root)
    # Standard SNMP trap port is 162, but requires root privileges
    trap_dest = ('localhost', 1162)
    
    print("=" * 60)
    print("SNMP Trap Sender - Test Script")
    print("=" * 60)
    print(f"Trap destination: {trap_dest[0]}:{trap_dest[1]}")
    print(f"Community: public")
    print()
    print("To receive these traps, run in another terminal:")
    print("  python trap_receiver.py")
    print()
    print("Or use tcpdump to monitor:")
    print(f"  sudo tcpdump -i lo -n port {trap_dest[1]}")
    print("=" * 60)
    print()
    
    # Test 1: String trap
    print("Test 1: Sending string trap...")
    await send_trap(
        trap_dest,
        (1, 3, 6, 1, 4, 1, 99999, 1, 0),  # myString OID
        v2c.OctetString('Alert: Test trap message'),
        'trap'
    )
    await asyncio.sleep(1)
    
    # Test 2: Integer trap
    print("\nTest 2: Sending integer trap...")
    await send_trap(
        trap_dest,
        (1, 3, 6, 1, 4, 1, 99999, 2, 0),  # myCounter OID
        v2c.Integer(999),
        'trap'
    )
    await asyncio.sleep(1)
    
    # Test 3: Counter32 trap
    print("\nTest 3: Sending Counter32 trap...")
    await send_trap(
        trap_dest,
        (1, 3, 6, 1, 4, 1, 99999, 5, 0),  # Counter32 OID
        v2c.Counter32(54321),
        'trap'
    )
    await asyncio.sleep(1)
    
    # Test 4: Gauge32 trap
    print("\nTest 4: Sending Gauge32 trap (high temperature)...")
    await send_trap(
        trap_dest,
        (1, 3, 6, 1, 4, 1, 99999, 6, 0),  # Gauge32 OID
        v2c.Gauge32(95),  # 95% - high value alert
        'trap'
    )
    await asyncio.sleep(1)
    
    # Test 5: IpAddress trap
    print("\nTest 5: Sending IpAddress trap...")
    await send_trap(
        trap_dest,
        (1, 3, 6, 1, 4, 1, 99999, 8, 0),  # IpAddress OID
        v2c.IpAddress('10.0.0.1'),
        'trap'
    )
    
    print("\n" + "=" * 60)
    print("All test traps sent!")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())

