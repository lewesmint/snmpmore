import unittest
import sys
from unittest.mock import patch, MagicMock
from io import StringIO


class TestCompileMib(unittest.TestCase):
    """Test suite for compile_mib module."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Remove compile_mib from sys.modules if it exists to allow fresh import
        if 'compile_mib' in sys.modules:
            del sys.modules['compile_mib']

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Remove compile_mib from sys.modules after test
        if 'compile_mib' in sys.modules:
            del sys.modules['compile_mib']

    def _import_with_mocks(self, mock_results: dict[str, str]) -> str:
        """Helper to import compile_mib with mocked compiler results."""
        captured_output = StringIO()

        with patch('pysmi.compiler.MibCompiler') as mock_compiler_class:
            mock_compiler = MagicMock()
            mock_compiler_class.return_value = mock_compiler
            mock_compiler.compile.return_value = mock_results

            with patch('sys.stdout', captured_output):
                try:
                    __import__("compile_mib")  # noqa: F401  # Import for side effects only
                except SystemExit:
                    pass  # Expected for some tests

        return captured_output.getvalue()

    def test_compile_mib_success(self) -> None:
        """Test successful MIB compilation."""
        mock_results = {'MY-AGENT-MIB': 'compiled'}
        output = self._import_with_mocks(mock_results)

        # Verify output
        self.assertIn('MY-AGENT-MIB: compiled', output)

    def test_compile_mib_failure(self) -> None:
        """Test MIB compilation failure."""
        mock_results = {'MY-AGENT-MIB': 'failed'}
        output = self._import_with_mocks(mock_results)

        # Verify output
        self.assertIn('MY-AGENT-MIB: failed', output)

    def test_compile_mib_partial_success(self) -> None:
        """Test MIB compilation with partial success."""
        mock_results = {
            'MY-AGENT-MIB': 'compiled',
            'SNMPv2-SMI': 'missing'
        }
        output = self._import_with_mocks(mock_results)

        # Verify output contains both results
        self.assertIn('MY-AGENT-MIB: compiled', output)
        self.assertIn('SNMPv2-SMI: missing', output)


if __name__ == '__main__':
    unittest.main()

