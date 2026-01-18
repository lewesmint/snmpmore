#!/usr/bin/env python3
"""
Simple SNMP agent that implements basic system group objects.
This is a minimal example showing the basics of pysnmp without complexity.

The agent provides standard SNMPv2-MIB system group objects:
- sysDescr (.1.3.6.1.2.1.1.1.0) - System description
- sysObjectID (.1.3.6.1.2.1.1.2.0) - System object identifier
- sysUpTime (.1.3.6.1.2.1.1.3.0) - System uptime
- sysContact (.1.3.6.1.2.1.1.4.0) - System contact
- sysName (.1.3.6.1.2.1.1.5.0) - System name
- sysLocation (.1.3.6.1.2.1.1.6.0) - System location

Run this agent and query it with:
    snmpget -v2c -c public localhost:10161 .1.3.6.1.2.1.1.1.0
    snmpwalk -v2c -c public localhost:10161 .1.3.6.1.2.1.1
"""

from typing import Any
import time
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import cmdrsp, context
from pyasn1.type.univ import OctetString, Integer, ObjectIdentifier


def create_simple_agent(host: str = '127.0.0.1', port: int = 10161) -> Any:
    """Create a simple SNMP agent that serves basic system group objects."""

    # Create SNMP engine
    snmpEngine = engine.SnmpEngine()

    # Setup transport endpoint (UDP on specified port)
    config.add_transport(
        snmpEngine,
        udp.DOMAIN_NAME,
        udp.UdpTransport().open_server_mode((host, port))
    )

    # Setup community 'public' with read-only access
    config.add_v1_system(snmpEngine, 'my-area', 'public')

    # Allow full read access to the system group
    config.add_vacm_user(
        snmpEngine,
        2,  # SNMPv2c
        'my-area',
        'noAuthNoPriv',
        (1, 3, 6, 1, 2, 1, 1),  # Read access to system group
        ()                       # No write access
    )

    # Get MIB builder
    mibBuilder = snmpEngine.get_mib_builder()

    # Import MIB classes from SNMPv2-SMI
    (MibScalar, MibScalarInstance) = mibBuilder.import_symbols(
        'SNMPv2-SMI',
        'MibScalar',
        'MibScalarInstance'
    )

    # Track start time for sysUpTime
    start_time = int(time.time() * 100)  # Convert to hundredths of seconds

    # Register system group objects
    # These are the standard SNMPv2-MIB system group objects
    mibBuilder.export_symbols(
        '__MY_SIMPLE_MIB',

        # sysDescr (.1.3.6.1.2.1.1.1.0) - System description
        MibScalar((1, 3, 6, 1, 2, 1, 1, 1), OctetString()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 1), (0,),
            OctetString('Simple Python SNMP Agent - Demo System')
        ),

        # sysObjectID (.1.3.6.1.2.1.1.2.0) - System object identifier
        MibScalar((1, 3, 6, 1, 2, 1, 1, 2), ObjectIdentifier()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 2), (0,),
            ObjectIdentifier('1.3.6.1.4.1.99999')  # Private enterprise number
        ),

        # sysUpTime (.1.3.6.1.2.1.1.3.0) - System uptime in hundredths of seconds
        MibScalar((1, 3, 6, 1, 2, 1, 1, 3), Integer()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 3), (0,),
            Integer(start_time)
        ),

        # sysContact (.1.3.6.1.2.1.1.4.0) - System contact
        MibScalar((1, 3, 6, 1, 2, 1, 1, 4), OctetString()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 4), (0,),
            OctetString('Admin <admin@example.com>')
        ),

        # sysName (.1.3.6.1.2.1.1.5.0) - System name
        MibScalar((1, 3, 6, 1, 2, 1, 1, 5), OctetString()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 5), (0,),
            OctetString('simple-snmp-agent')
        ),

        # sysLocation (.1.3.6.1.2.1.1.6.0) - System location
        MibScalar((1, 3, 6, 1, 2, 1, 1, 6), OctetString()),
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 6), (0,),
            OctetString('Development Lab')
        ),
    )

    # Register SNMP command responders (GET, GETNEXT, etc.)
    snmpContext = context.SnmpContext(snmpEngine)
    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
    cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)

    return snmpEngine


def main() -> None:
    """Run the simple SNMP agent."""
    host = '127.0.0.1'
    port = 10161

    print(f'Starting simple SNMP agent on {host}:{port}')
    print(f'Serving SNMPv2-MIB system group objects')
    print()
    print('Test with:')
    print(f'  snmpget -v2c -c public {host}:{port} .1.3.6.1.2.1.1.1.0')
    print(f'  snmpget -v2c -c public {host}:{port} SNMPv2-MIB::sysDescr.0')
    print(f'  snmpwalk -v2c -c public {host}:{port} .1.3.6.1.2.1.1')
    print(f'  snmpwalk -v2c -c public {host}:{port} SNMPv2-MIB::system')
    print()
    print('Press Ctrl+C to stop')
    
    # Create the agent
    snmpEngine = create_simple_agent(host, port)
    
    # Run the agent
    try:
        snmpEngine.transport_dispatcher.job_started(1)
        snmpEngine.transport_dispatcher.run_dispatcher()
    except KeyboardInterrupt:
        print('\nStopping agent...')
    finally:
        snmpEngine.transport_dispatcher.close_dispatcher()


if __name__ == '__main__':
    main()

