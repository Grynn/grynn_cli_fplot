import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from grynn_fplot.cli import display_plot


class TestCliOptions(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_version_flag(self):
        """Test that version flag works"""
        result = self.runner.invoke(display_plot, ['--version'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('fplot', result.output)

    def test_missing_ticker(self):
        """Test error when no ticker is provided"""
        result = self.runner.invoke(display_plot, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Missing argument', result.output)

    @patch('grynn_fplot.cli.format_options_for_display')
    def test_call_flag_with_options(self, mock_format):
        """Test --call flag with available options"""
        mock_format.return_value = ['AAPL 150C 30DTE', 'AAPL 155C 30DTE']
        
        result = self.runner.invoke(display_plot, ['AAPL', '--call'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('AAPL 150C 30DTE', result.output)
        self.assertIn('AAPL 155C 30DTE', result.output)
        mock_format.assert_called_once_with('AAPL', 'calls')

    @patch('grynn_fplot.cli.format_options_for_display')
    def test_call_flag_no_options(self, mock_format):
        """Test --call flag when no options are available"""
        mock_format.return_value = []
        
        result = self.runner.invoke(display_plot, ['AAPL', '--call'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('No call options found', result.output)

    @patch('grynn_fplot.cli.format_options_for_display')
    def test_put_flag_with_options(self, mock_format):
        """Test --put flag with available options"""
        mock_format.return_value = ['AAPL 150P 30DTE', 'AAPL 145P 30DTE']
        
        result = self.runner.invoke(display_plot, ['AAPL', '--put'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('AAPL 150P 30DTE', result.output)
        self.assertIn('AAPL 145P 30DTE', result.output)
        mock_format.assert_called_once_with('AAPL', 'puts')

    @patch('grynn_fplot.cli.format_options_for_display')
    def test_put_flag_no_options(self, mock_format):
        """Test --put flag when no options are available"""
        mock_format.return_value = []
        
        result = self.runner.invoke(display_plot, ['AAPL', '--put'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('No put options found', result.output)


if __name__ == "__main__":
    unittest.main()