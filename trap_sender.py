import logging
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, NotificationType, send_notification
from pysnmp.smi import builder
from typing import Tuple, Any, Literal, cast, Optional, List
import asyncio


class TrapSender:
    """
    Encapsulates SNMP trap sending using pysnmp.
    Handles error checking, logging, and input validation.
    """
    def __init__(self, mibBuilder: 'builder.MibBuilder', dest: Tuple[str, int] = ('localhost', 162), community: str = 'public'):
        """
        :param mibBuilder: pysnmp MibBuilder instance
        :param dest: Tuple of (host, port) for trap destination
        :param community: SNMP community string
        """
        self.snmpEngine = SnmpEngine()
        self.dest = dest
        self.community = community
        self.mibBuilder = mibBuilder
        self.logger = logging.getLogger(__name__)

    def send_trap(self, oid: Tuple[int, ...], value: Any, trap_type: Literal['trap', 'inform'] = 'inform') -> None:
        """
        Send an SNMP trap or inform.
        :param oid: OID tuple for the trap
        :param value: Value to send with the trap
        :param trap_type: 'trap' or 'inform'
        """
        if trap_type not in ('trap', 'inform'):
            self.logger.error(f"Invalid trap_type '{trap_type}'. Must be 'trap' or 'inform'.")
            return
        try:
            mib_symbols: Tuple[Any, ...] = self.mibBuilder.import_symbols('__MY_MIB', oid)
            mib_symbol = mib_symbols[0]
        except Exception as e:
            self.logger.error(f"Failed to import MIB symbol for OID {oid}: {e}")
            return
        try:
            # Run the async send in a new event loop
            async def _send() -> Any:
                result = await send_notification(
                    self.snmpEngine,
                    CommunityData(self.community),
                    await UdpTransportTarget.create(self.dest),
                    ContextData(),
                    trap_type,
                    NotificationType(mib_symbol).add_var_binds((oid, value))
                )
                errorIndication = cast(Tuple[Optional[str], int, int, List[Tuple[Any, Any]]], result)[0]
                return errorIndication

            errorIndication = asyncio.run(_send())
            if errorIndication:
                self.logger.error(f'Trap send error: {errorIndication}')
            else:
                self.logger.info(f'Trap sent to {self.dest} for OID {oid} with value {value}')
        except Exception as e:
            self.logger.exception(f"Exception while sending SNMP trap: {e}")
