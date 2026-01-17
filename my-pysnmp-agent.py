#!/usr/bin/env python3
"""
SNMP agent using pysnmp that exposes scalars and tables as defined in MY-AGENT-MIB.
Listens on UDP port 10161 (non-privileged) and responds to SNMP queries.
"""

import threading
import asyncio
import time
import logging
from typing import Any, Tuple
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.smi import builder
from pysnmp.entity.rfc3413 import cmdrsp, context
from pyasn1.type.univ import OctetString, Integer
from pysnmp.proto.api import v2c
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, NotificationType, send_notification
)
# Import SNMP data types
Counter32 = v2c.Counter32
Counter64 = v2c.Counter64
Gauge32 = v2c.Gauge32
TimeTicks = v2c.TimeTicks
IpAddress = v2c.IpAddress
Unsigned32 = v2c.Unsigned32
Integer32 = v2c.Integer32

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class SNMPAgent:
    """SNMP Agent that serves enterprise MIB data."""

    def __init__(self, host: str = '127.0.0.1', port: int = 10161) -> None:
        """Initialize the SNMP agent.

        Args:
            host: IP address to bind to
            port: UDP port to listen on (default 10161 for non-root)
        """
        self.host = host
        self.port = port
        self.snmpEngine = engine.SnmpEngine()
        self.mibBuilder = self.snmpEngine.get_mib_builder()

        # Add MIB sources
        self.mibBuilder.add_mib_sources(builder.DirMibSource('./mibs'))

        # Import MIB classes the pysnmp v7+ way
        (self.MibScalar, self.MibScalarInstance, self.MibTable,
         self.MibTableRow, self.MibTableColumn) = self.mibBuilder.import_symbols(
            'SNMPv2-SMI', 'MibScalar', 'MibScalarInstance', 'MibTable',
            'MibTableRow', 'MibTableColumn'
        )

        # Counter for dynamic scalar
        self.counter = 0
        self.counter_lock = threading.Lock()

        # Start time for TimeTicks
        self.start_time = time.time()

        # Table data
        self.table_rows = [
            [1, 'sensor_a', 25, 'ok'],
            [2, 'sensor_b', 30, 'ok'],
            [3, 'sensor_c', 45, 'warning'],
        ]

        self._setup_transport()
        self._setup_community()
        self._setup_responders()
        self._register_mib_objects()

    def _setup_transport(self) -> None:
        """Configure UDP transport."""
        config.add_transport(
            self.snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode((self.host, self.port))
        )

    def _setup_community(self) -> None:
        """Configure SNMPv2c community."""
        config.add_v1_system(self.snmpEngine, 'my-area', 'public')

        # Allow full access to enterprise subtree
        config.add_vacm_user(
            self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
            (1, 3, 6, 1, 4, 1, 99999)
        )

    def _setup_responders(self) -> None:
        """Setup SNMP command responders."""
        snmpContext = context.SnmpContext(self.snmpEngine)
        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.SetCommandResponder(self.snmpEngine, snmpContext)

    def _get_counter(self, *args: Any) -> Integer:
        """Dynamic counter that increments on each GET."""
        with self.counter_lock:
            self.counter += 1
            return Integer(self.counter)

    def _register_mib_objects(self) -> None:
        """Register all MIB objects (scalars and table)."""
        # Create a custom MibScalarInstance class for dynamic counter
        class DynamicCounterInstance(self.MibScalarInstance):
            def getValue(self, name: Any, **context: Any) -> Integer:
                with self.agent.counter_lock:
                    self.agent.counter += 1
                    return Integer(self.agent.counter)

        # Create a custom MibScalarInstance class for TimeTicks (uptime)
        class UptimeInstance(self.MibScalarInstance):
            def getValue(self, name: Any, **context: Any) -> TimeTicks:
                uptime_seconds = int(time.time() - self.agent.start_time)
                # TimeTicks is in hundredths of a second
                return TimeTicks(uptime_seconds * 100)

        # Store reference to self for the dynamic instances
        DynamicCounterInstance.agent = self
        UptimeInstance.agent = self

        # Scalars under .1.3.6.1.4.1.99999
        # First create MibScalar objects, then MibScalarInstance objects
        self.mibBuilder.export_symbols(
            '__MY_MIB',
            # myString (.1.3.6.1.4.1.99999.1.0) - OctetString
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 1), OctetString()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 1), (0,),
                OctetString('Hello from pysnmp')
            ),
            # myCounter (.1.3.6.1.4.1.99999.2.0) - Integer (dynamic)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 2), Integer()),
            DynamicCounterInstance(
                (1, 3, 6, 1, 4, 1, 99999, 2), (0,),
                Integer(0)
            ),
            # myGauge (.1.3.6.1.4.1.99999.3.0) - Integer
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 3), Integer()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 3), (0,),
                Integer(42)
            ),
            # Additional data types for testing
            # Counter32 (.1.3.6.1.4.1.99999.5.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 5), Counter32()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 5), (0,),
                Counter32(12345)
            ),
            # Gauge32 (.1.3.6.1.4.1.99999.6.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 6), Gauge32()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 6), (0,),
                Gauge32(75)
            ),
            # TimeTicks (.1.3.6.1.4.1.99999.7.0) - uptime in hundredths of a second
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 7), TimeTicks()),
            UptimeInstance(
                (1, 3, 6, 1, 4, 1, 99999, 7), (0,),
                TimeTicks(0)
            ),
            # IpAddress (.1.3.6.1.4.1.99999.8.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 8), IpAddress()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 8), (0,),
                IpAddress('192.168.1.100')
            ),
            # Counter64 (.1.3.6.1.4.1.99999.9.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 9), Counter64()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 9), (0,),
                Counter64(9876543210)
            ),
            # Unsigned32 (.1.3.6.1.4.1.99999.10.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 10), Unsigned32()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 10), (0,),
                Unsigned32(4294967295)  # Max value for Unsigned32
            ),
            # Integer32 (.1.3.6.1.4.1.99999.11.0)
            self.MibScalar((1, 3, 6, 1, 4, 1, 99999, 11), Integer32()),
            self.MibScalarInstance(
                (1, 3, 6, 1, 4, 1, 99999, 11), (0,),
                Integer32(-2147483648)  # Min value for Integer32
            ),
        )

        # Table under .1.3.6.1.4.1.99999.4.1
        # First define the table structure
        self.mibBuilder.export_symbols(
            '__MY_MIB',
            # myTable (.1.3.6.1.4.1.99999.4)
            myTable=self.MibTable((1, 3, 6, 1, 4, 1, 99999, 4)),
            # myTableEntry (.1.3.6.1.4.1.99999.4.1)
            myTableEntry=self.MibTableRow((1, 3, 6, 1, 4, 1, 99999, 4, 1)).setIndexNames(
                (0, '__MY_MIB', 'myTableIndex')
            ),
            # myTableIndex (.1.3.6.1.4.1.99999.4.1.1)
            myTableIndex=self.MibTableColumn((1, 3, 6, 1, 4, 1, 99999, 4, 1, 1), Integer()),
            # myTableName (.1.3.6.1.4.1.99999.4.1.2)
            myTableName=self.MibTableColumn((1, 3, 6, 1, 4, 1, 99999, 4, 1, 2), OctetString()),
            # myTableValue (.1.3.6.1.4.1.99999.4.1.3)
            myTableValue=self.MibTableColumn((1, 3, 6, 1, 4, 1, 99999, 4, 1, 3), Integer()),
            # myTableStatus (.1.3.6.1.4.1.99999.4.1.4)
            myTableStatus=self.MibTableColumn((1, 3, 6, 1, 4, 1, 99999, 4, 1, 4), OctetString()),
        )

        # Now populate the table with data using MIB instrumentation
        snmpContext = context.SnmpContext(self.snmpEngine)
        mibInstrumentation = snmpContext.get_mib_instrum()

        # Import the table columns we just defined
        (myTableEntry, myTableIndex, myTableName,
         myTableValue, myTableStatus) = self.mibBuilder.import_symbols(
            '__MY_MIB', 'myTableEntry', 'myTableIndex', 'myTableName',
            'myTableValue', 'myTableStatus'
        )

        # Populate each row
        for row in self.table_rows:
            idx, name, value, status = row
            rowInstanceId = myTableEntry.getInstIdFromIndices(idx)
            mibInstrumentation.write_variables(
                (myTableIndex.name + rowInstanceId, idx),
                (myTableName.name + rowInstanceId, name),
                (myTableValue.name + rowInstanceId, value),
                (myTableStatus.name + rowInstanceId, status),
            )

    def run(self) -> None:
        """Run the SNMP agent (blocking)."""
        print(f'SNMP agent running on {self.host}:{self.port}')
        print(f'Community: public')
        print(f'Enterprise OID: .1.3.6.1.4.1.99999')
        print(f'Try: snmpwalk -v2c -c public {self.host}:{self.port} .1.3.6.1.4.1.99999')
        print('Press Ctrl+C to stop')

        self.snmpEngine.transport_dispatcher.job_started(1)
        try:
            # For pysnmp v7 with asyncio, we need to run the event loop
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            print('\nShutting down agent')
        finally:
            self.snmpEngine.transport_dispatcher.close_dispatcher()

    def stop(self) -> None:
        """Stop the SNMP agent."""
        self.snmpEngine.transport_dispatcher.close_dispatcher()

    async def send_trap_async(self, trap_dest: Tuple[str, int], oid: Tuple[int, ...],
                              value: Any, trap_type: str = 'trap') -> None:
        """Send an SNMP trap or inform notification.

        Args:
            trap_dest: Tuple of (host, port) for trap destination
            oid: OID tuple for the trap variable binding
            value: Value to send with the trap
            trap_type: 'trap' or 'inform'
        """
        logger = logging.getLogger(__name__)
        try:
            # Create a notification type with the OID and value
            result = await send_notification(
                SnmpEngine(),
                CommunityData('public'),
                await UdpTransportTarget.create(trap_dest),
                ContextData(),
                trap_type,
                NotificationType((1, 3, 6, 1, 6, 3, 1, 1, 5, 1)).add_var_binds((oid, value))
            )

            errorIndication = result[0]
            if errorIndication:
                logger.error(f'Trap send error: {errorIndication}')
            else:
                logger.info(f'Trap sent to {trap_dest} for OID {oid} with value {value}')
        except Exception as e:
            logger.error(f'Exception sending trap: {e}')

    def send_trap(self, trap_dest: Tuple[str, int], oid: Tuple[int, ...],
                  value: Any, trap_type: str = 'trap') -> None:
        """Send an SNMP trap synchronously (wrapper for async method).

        Args:
            trap_dest: Tuple of (host, port) for trap destination
            oid: OID tuple for the trap variable binding
            value: Value to send with the trap
            trap_type: 'trap' or 'inform'
        """
        asyncio.run(self.send_trap_async(trap_dest, oid, value, trap_type))


def main() -> None:
    """Main entry point."""
    agent = SNMPAgent()
    agent.run()


if __name__ == "__main__":
    main()
