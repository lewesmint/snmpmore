#!/usr/bin/env python3
"""
Simple SNMP trap receiver for testing.
Listens for SNMP traps and displays them.
"""

import asyncio
import logging
from typing import Any
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.rfc1902 import OctetString

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TrapReceiver:
    """Simple SNMP trap receiver."""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 162) -> None:
        """Initialize the trap receiver.

        Args:
            host: IP address to bind to (0.0.0.0 for all interfaces)
            port: Port to listen on (default 162, standard SNMP trap port)
        """
        self.host = host
        self.port = port
        self.snmpEngine = engine.SnmpEngine()
        
    def setup(self) -> None:
        """Setup the trap receiver."""
        # Transport setup
        config.add_transport(
            self.snmpEngine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode((self.host, self.port))
        )
        
        # SNMPv1/v2c setup
        config.add_v1_system(self.snmpEngine, 'my-area', 'public')
        
        # Register callback for trap reception
        ntfrcv.NotificationReceiver(self.snmpEngine, self.trap_callback)
        
        logger.info(f"Trap receiver listening on {self.host}:{self.port}")
        logger.info("Waiting for traps... (Press Ctrl+C to stop)")
        
    def trap_callback(
        self,
        snmpEngine: 'engine.SnmpEngine',
        stateReference: Any,
        contextEngineId: OctetString,
        contextName: OctetString,
        varBinds: list[tuple[Any, Any]],
        cbCtx: Any
    ) -> None:
        """Callback function called when a trap is received.

        Args:
            snmpEngine: SNMP engine instance
            stateReference: Unique reference to this notification
            contextEngineId: Context engine ID
            contextName: Context name
            varBinds: List of variable bindings (OID, value pairs)
            cbCtx: Callback context
        """
        print("\n" + "=" * 70)
        print("🔔 TRAP RECEIVED!")
        print("=" * 70)
        print(f"Context Engine ID: {contextEngineId.prettyPrint()}")
        print(f"Context Name: {contextName.prettyPrint()}")
        print("\nVariable Bindings:")
        print("-" * 70)

        for idx, varBind in enumerate(varBinds, 1):
            oid, value = varBind
            print(f"  {idx}. OID: {oid.prettyPrint()}")
            print(f"     Value: {value.prettyPrint()}")
            print(f"     Type: {type(value).__name__}")
            print()

        print("=" * 70)
        
    def run(self) -> None:
        """Run the trap receiver (blocking)."""
        self.setup()
        
        self.snmpEngine.transport_dispatcher.job_started(1)
        try:
            # Run the asyncio event loop
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            logger.info("\nShutting down trap receiver...")
        finally:
            self.snmpEngine.transport_dispatcher.close_dispatcher()


def main() -> None:
    """Main function."""
    print("=" * 70)
    print("SNMP Trap Receiver")
    print("=" * 70)
    print()
    print("NOTE: To listen on port 162 (standard SNMP trap port),")
    print("      you may need to run this script with sudo:")
    print("      sudo python trap_receiver.py")
    print()
    print("Or use a non-privileged port (>1024) by modifying the code.")
    print("=" * 70)
    print()
    
    # Use port 1162 instead of 162 to avoid needing root
    receiver = TrapReceiver(host='0.0.0.0', port=1162)
    receiver.run()


if __name__ == '__main__':
    main()

