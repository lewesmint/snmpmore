#!/usr/bin/env python3
"""
Simple SNMP agent that only implements sysDescr (system description).
This is a minimal example showing the basics of pysnmp without complexity.

The agent provides:
- sysDescr (.1.3.6.1.2.1.1.1.0) - A simple string describing the system

Run this agent and query it with:
    snmpget -v2c -c public localhost:161 .1.3.6.1.2.1.1.1.0
"""

from typing import Any
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import cmdrsp, context
from pyasn1.type.univ import OctetString


def create_simple_agent(host: str = '127.0.0.1', port: int = 10161) -> Any:
    """Create a simple SNMP agent that serves sysDescr."""
    
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
    
    # Register sysDescr (.1.3.6.1.2.1.1.1.0)
    # This is the standard system description object
    mibBuilder.export_symbols(
        '__MY_SIMPLE_MIB',
        # First define the scalar object
        MibScalar((1, 3, 6, 1, 2, 1, 1, 1), OctetString()),
        # Then define the instance with value
        MibScalarInstance(
            (1, 3, 6, 1, 2, 1, 1, 1),  # OID without .0
            (0,),                        # Instance ID (.0)
            OctetString('Simple Python SNMP Agent - Demo System')
        )
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
    print(f'Serving sysDescr at .1.3.6.1.2.1.1.1.0')
    print()
    print('Test with:')
    print(f'  snmpget -v2c -c public {host}:{port} .1.3.6.1.2.1.1.1.0')
    print(f'  snmpget -v2c -c public {host}:{port} SNMPv2-MIB::sysDescr.0')
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

