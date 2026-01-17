import unittest
import logging
from unittest.mock import MagicMock, patch, AsyncMock
from pysnmp.smi import builder
from pyasn1.type.univ import OctetString, Integer
from trap_sender import TrapSender


class TestTrapSender(unittest.TestCase):
    """Test suite for TrapSender class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mibBuilder = builder.MibBuilder()
        self.mibBuilder.load_modules('SNMPv2-SMI')
        self.trap_sender = TrapSender(
            self.mibBuilder,
            dest=('localhost', 162),
            community='public'
        )

    def test_init(self) -> None:
        """Test TrapSender initialization."""
        self.assertIsNotNone(self.trap_sender.snmpEngine)
        self.assertEqual(self.trap_sender.dest, ('localhost', 162))
        self.assertEqual(self.trap_sender.community, 'public')
        self.assertEqual(self.trap_sender.mibBuilder, self.mibBuilder)
        self.assertIsInstance(self.trap_sender.logger, logging.Logger)

    def test_init_with_custom_params(self) -> None:
        """Test TrapSender initialization with custom parameters."""
        custom_sender = TrapSender(
            self.mibBuilder,
            dest=('192.168.1.1', 1162),
            community='private'
        )
        
        self.assertEqual(custom_sender.dest, ('192.168.1.1', 1162))
        self.assertEqual(custom_sender.community, 'private')

    @patch('trap_sender.send_notification')
    def test_send_trap_invalid_type(self, mock_send: MagicMock) -> None:
        """Test send_trap with invalid trap_type."""
        with patch.object(self.trap_sender.logger, 'error') as mock_error:
            self.trap_sender.send_trap(
                (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                OctetString('test'),
                trap_type='invalid'  # type: ignore
            )

            # Verify error was logged
            mock_error.assert_called_once()
            self.assertIn('Invalid trap_type', mock_error.call_args[0][0])

            # Verify send_notification was NOT called
            mock_send.assert_not_called()

    @patch('trap_sender.send_notification')
    def test_send_trap_mib_import_failure(self, mock_send: MagicMock) -> None:
        """Test send_trap when MIB symbol import fails."""
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.side_effect = Exception('Import failed')

            with patch.object(self.trap_sender.logger, 'error') as mock_error:
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    OctetString('test'),
                    trap_type='trap'
                )

                # Verify error was logged
                mock_error.assert_called_once()
                self.assertIn('Failed to import MIB symbol', mock_error.call_args[0][0])

                # Verify send_notification was NOT called
                mock_send.assert_not_called()

    @patch('trap_sender.asyncio.run')
    @patch('trap_sender.send_notification')
    def test_send_trap_success_trap(self, mock_send: MagicMock, mock_run: MagicMock) -> None:
        """Test successful trap send."""
        # Mock successful send (no error indication)
        async def mock_send_result() -> tuple[None | str, int, int, list[object]]:
            return (None, 0, 0, [])
        mock_send.return_value = mock_send_result()
        mock_run.return_value = None  # No error indication

        # Mock MIB symbol import
        mock_symbol = MagicMock()
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.return_value = [mock_symbol]

            with patch.object(self.trap_sender.logger, 'info') as mock_info:
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    OctetString('test'),
                    trap_type='trap'
                )

                # Verify asyncio.run was called
                mock_run.assert_called_once()

                # Verify success was logged
                mock_info.assert_called_once()
                self.assertIn('Trap sent', mock_info.call_args[0][0])

    @patch('trap_sender.asyncio.run')
    @patch('trap_sender.send_notification')
    def test_send_trap_success_inform(self, mock_send: MagicMock, mock_run: MagicMock) -> None:
        """Test successful inform send."""
        # Mock successful send (no error indication)
        async def mock_send_result() -> tuple[None | str, int, int, list[object]]:
            return (None, 0, 0, [])
        mock_send.return_value = mock_send_result()
        mock_run.return_value = None  # No error indication

        # Mock MIB symbol import
        mock_symbol = MagicMock()
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.return_value = [mock_symbol]

            with patch.object(self.trap_sender.logger, 'info') as mock_info:
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    Integer(42),
                    trap_type='inform'
                )

                # Verify asyncio.run was called
                mock_run.assert_called_once()

                # Verify success was logged
                mock_info.assert_called_once()
                self.assertIn('Trap sent', mock_info.call_args[0][0])

    @patch('trap_sender.asyncio.run')
    @patch('trap_sender.send_notification')
    def test_send_trap_with_error_indication(self, mock_send: MagicMock, mock_run: MagicMock) -> None:
        """Test send_trap when sendNotification returns an error."""
        # Mock error indication
        async def mock_send_result() -> tuple[str, int, int, list[object]]:
            return ('Network timeout', 0, 0, [])
        mock_send.return_value = mock_send_result()
        mock_run.return_value = 'Network timeout'

        # Mock MIB symbol import
        mock_symbol = MagicMock()
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.return_value = [mock_symbol]

            with patch.object(self.trap_sender.logger, 'error') as mock_error:
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    OctetString('test'),
                    trap_type='trap'
                )

                # Verify error was logged
                mock_error.assert_called_once()
                self.assertIn('Trap send error', mock_error.call_args[0][0])

    @patch('trap_sender.asyncio.run')
    def test_send_trap_exception_during_send(self, mock_run: MagicMock) -> None:
        """Test send_trap when an exception occurs during send."""
        # Mock exception during send
        mock_run.side_effect = RuntimeError('Connection failed')

        # Mock MIB symbol import
        mock_symbol = MagicMock()
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.return_value = [mock_symbol]

            with patch.object(self.trap_sender.logger, 'exception') as mock_exception:
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    OctetString('test'),
                    trap_type='inform'
                )

                # Verify exception was logged
                mock_exception.assert_called_once()
                self.assertIn('Exception while sending SNMP trap', mock_exception.call_args[0][0])

    @patch('trap_sender.NotificationType')
    @patch('trap_sender.UdpTransportTarget.create', new_callable=AsyncMock)
    @patch('trap_sender.send_notification', new_callable=AsyncMock)
    def test_send_trap_executes_async_send(self, mock_send: AsyncMock, mock_udp: AsyncMock, mock_notif: MagicMock) -> None:
        """Test that the async _send function is actually executed."""
        # Configure async mocks to return proper values
        mock_send.return_value = (None, 0, 0, [])
        mock_udp.return_value = MagicMock()

        # Mock NotificationType
        mock_notif_instance = MagicMock()
        mock_notif_instance.add_var_binds.return_value = mock_notif_instance
        mock_notif.return_value = mock_notif_instance

        # Mock MIB symbol import
        mock_symbol = MagicMock()
        with patch.object(self.trap_sender.mibBuilder, 'import_symbols') as mock_import:
            mock_import.return_value = [mock_symbol]

            with patch.object(self.trap_sender.logger, 'info') as mock_info:
                # This will actually run asyncio.run and execute _send()
                self.trap_sender.send_trap(
                    (1, 3, 6, 1, 4, 1, 99999, 1, 0),
                    OctetString('test'),
                    trap_type='trap'
                )

                # Verify send_notification was called (proves _send was executed)
                mock_send.assert_called_once()
                mock_udp.assert_called_once()

                # Verify success was logged
                mock_info.assert_called_once()


if __name__ == '__main__':
    unittest.main()

