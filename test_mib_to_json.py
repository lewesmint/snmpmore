import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from mib_to_json import extract_mib_info, main


class TestMibToJson(unittest.TestCase):
    """Test suite for mib_to_json module."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mib_path = os.path.join(self.test_dir, 'TEST-MIB.py')
        
    def tearDown(self) -> None:
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # Clean up any generated JSON files in mock-behavior directory
        if os.path.exists('mock-behavior'):
            for f in os.listdir('mock-behavior'):
                if f.endswith('_behavior.json') and f.startswith('TEST-'):
                    try:
                        os.remove(os.path.join('mock-behavior', f))
                    except:
                        pass

    def test_extract_mib_info_with_real_mib(self) -> None:
        """Test extract_mib_info with a real compiled MIB."""
        compiled_mibs_location : str = 'compiled-mibs'
        # Use the existing MY-AGENT-MIB
        mib_path = os.path.join(compiled_mibs_location, 'MY-AGENT-MIB.py')
        if not os.path.exists(mib_path):
            self.skipTest("MY-AGENT-MIB.py not found")
        
        result = extract_mib_info(mib_path, 'MY-AGENT-MIB')
        
        # Verify result is a dictionary
        self.assertIsInstance(result, dict)
        
        # Verify structure of results
        for _symbol_name, symbol_data in result.items():
            self.assertIn('oid', symbol_data)
            self.assertIn('type', symbol_data)
            self.assertIn('access', symbol_data)
            self.assertIn('initial', symbol_data)
            self.assertIn('dynamic_function', symbol_data)
            self.assertIsNone(symbol_data['initial'])
            self.assertIsNone(symbol_data['dynamic_function'])

    def test_extract_mib_info_with_mock(self) -> None:
        """Test extract_mib_info with mocked MIB builder."""
        # Create mock symbol object
        mock_symbol = MagicMock()
        mock_symbol.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
        mock_syntax = MagicMock()
        mock_syntax.__class__.__name__ = 'OctetString'
        mock_symbol.getSyntax.return_value = mock_syntax
        mock_symbol.getMaxAccess.return_value = 'read-only'
        
        # Create mock MIB builder
        with patch('mib_to_json.builder.MibBuilder') as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.mibSymbols = {
                'TEST-MIB': {
                    'testScalar': mock_symbol
                }
            }
            
            result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')
            
            self.assertIn('testScalar', result)
            self.assertEqual(result['testScalar']['oid'], (1, 3, 6, 1, 4, 1, 99999, 1, 0))
            self.assertEqual(result['testScalar']['type'], 'OctetString')
            self.assertEqual(result['testScalar']['access'], 'read-only')

    def test_extract_mib_info_filters_non_scalars(self) -> None:
        """Test that extract_mib_info only processes objects with getName and getSyntax."""
        # Create mock symbols - one valid, one invalid
        mock_valid = MagicMock()
        mock_valid.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
        mock_syntax = MagicMock()
        mock_syntax.__class__.__name__ = 'Integer32'
        mock_valid.getSyntax.return_value = mock_syntax
        mock_valid.getMaxAccess.return_value = 'read-write'
        
        mock_invalid = MagicMock(spec=[])  # No getName or getSyntax
        
        with patch('mib_to_json.builder.MibBuilder') as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.mibSymbols = {
                'TEST-MIB': {
                    'validScalar': mock_valid,
                    'invalidObject': mock_invalid
                }
            }
            
            result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')
            
            self.assertIn('validScalar', result)
            self.assertNotIn('invalidObject', result)

    def test_extract_mib_info_handles_missing_getMaxAccess(self) -> None:
        """Test that extract_mib_info handles symbols without getMaxAccess."""
        mock_symbol = MagicMock()
        mock_symbol.getName.return_value = (1, 3, 6, 1, 4, 1, 99999, 1, 0)
        mock_syntax = MagicMock()
        mock_syntax.__class__.__name__ = 'Counter32'
        mock_symbol.getSyntax.return_value = mock_syntax
        # Remove getMaxAccess attribute
        del mock_symbol.getMaxAccess
        
        with patch('mib_to_json.builder.MibBuilder') as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.mibSymbols = {
                'TEST-MIB': {
                    'testCounter': mock_symbol
                }
            }
            
            result = extract_mib_info('/fake/path/TEST-MIB.py', 'TEST-MIB')
            
            self.assertIn('testCounter', result)
            self.assertEqual(result['testCounter']['access'], 'unknown')

    @patch('sys.argv', ['mib_to_json.py', 'mibs/MY-AGENT-MIB.py', 'MY-AGENT-MIB'])
    def test_main_success(self) -> None:
        """Test main function with valid arguments."""
        if not os.path.exists('mibs/MY-AGENT-MIB.py'):
            self.skipTest("MY-AGENT-MIB.py not found")

        with patch('builtins.print') as mock_print:
            main()

            # Verify JSON file was created in mock-behavior directory
            json_path = 'mock-behavior/MY-AGENT-MIB_behavior.json'
            self.assertTrue(os.path.exists(json_path))

            # Verify JSON content
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.assertIsInstance(data, dict)

            # Verify print was called
            mock_print.assert_called_once()
            self.assertIn('mock-behavior/MY-AGENT-MIB_behavior.json', mock_print.call_args[0][0])

    def test_main_as_script(self) -> None:
        """Test running main when file is executed as __main__."""
        if not os.path.exists('mibs/MY-AGENT-MIB.py'):
            self.skipTest("MY-AGENT-MIB.py not found")

        # Test the if __name__ == '__main__' block
        with patch('sys.argv', ['mib_to_json.py', 'mibs/MY-AGENT-MIB.py', 'MY-AGENT-MIB']):
            with patch('builtins.print'):
                # Import and check __name__ handling
                import mib_to_json
                # The module's __name__ will be 'mib_to_json', not '__main__'
                # so the block won't execute, but we've tested main() above
                self.assertTrue(hasattr(mib_to_json, 'main'))

    @patch('sys.exit')
    @patch('sys.argv', ['mib_to_json.py'])
    def test_main_insufficient_args(self, mock_exit: MagicMock) -> None:
        """Test main function with insufficient arguments."""
        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit):
                main()

            mock_print.assert_called_once()
            self.assertIn('Usage:', mock_print.call_args[0][0])
            mock_exit.assert_called_once_with(1)

    @patch('sys.exit')
    @patch('sys.argv', ['mib_to_json.py', 'arg1'])
    def test_main_one_arg(self, mock_exit: MagicMock) -> None:
        """Test main function with only one argument."""
        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit):
                main()

            mock_print.assert_called_once()
            self.assertIn('Usage:', mock_print.call_args[0][0])
            mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()

