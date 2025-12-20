import unittest
from unittest.mock import patch
from click.testing import CliRunner
from grynn_fplot.cli import display_plot


class TestCliOptions(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_version_flag(self):
        """Test that version flag works"""
        result = self.runner.invoke(display_plot, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("fplot", result.output)

    def test_missing_ticker(self):
        """Test error when no ticker is provided"""
        result = self.runner.invoke(display_plot, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_call_flag_with_options(self, mock_format):
        """Test --call flag with available options"""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)", "AAPL 155C 30DTE ($3.00, 25.1%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AAPL 150C 30DTE", result.output)
        self.assertIn("AAPL 155C 30DTE", result.output)
        mock_format.assert_called_once_with("AAPL", "calls", max_expiry="6m", min_dte=None, show_all=False, filter_ast=None)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_call_flag_no_options(self, mock_format):
        """Test --call flag when no options are available"""
        mock_format.return_value = []

        result = self.runner.invoke(display_plot, ["AAPL", "--call"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No call options found", result.output)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_put_flag_with_options(self, mock_format):
        """Test --put flag with available options"""
        mock_format.return_value = ["AAPL 150P 30DTE ($3.50, 8.2%)", "AAPL 145P 30DTE ($2.00, 12.1%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--put"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AAPL 150P 30DTE", result.output)
        self.assertIn("AAPL 145P 30DTE", result.output)
        mock_format.assert_called_once_with("AAPL", "puts", max_expiry="6m", min_dte=None, show_all=False, filter_ast=None)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_put_flag_no_options(self, mock_format):
        """Test --put flag when no options are available"""
        mock_format.return_value = []

        result = self.runner.invoke(display_plot, ["AAPL", "--put"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No put options found", result.output)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_max_expiry_flag(self, mock_format):
        """Test --max flag for expiry filtering"""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--max", "3m"])
        self.assertEqual(result.exit_code, 0)
        mock_format.assert_called_once_with("AAPL", "calls", max_expiry="3m", min_dte=None, show_all=False, filter_ast=None)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_all_flag(self, mock_format):
        """Test --all flag to show all expiries"""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)", "AAPL 150C 365DTE ($10.00, 8.5%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--all"])
        self.assertEqual(result.exit_code, 0)
        mock_format.assert_called_once_with("AAPL", "calls", max_expiry="6m", min_dte=None, show_all=True, filter_ast=None)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_min_dte_flag(self, mock_format):
        """Test --min-dte flag for long-dated options"""
        mock_format.return_value = ["AAPL 150C 365DTE ($10.00, 8.5%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--min-dte", "300", "--all"])
        self.assertEqual(result.exit_code, 0)
        mock_format.assert_called_once_with("AAPL", "calls", max_expiry="6m", min_dte=300, show_all=True, filter_ast=None)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_filter_flag_simple(self, mock_format):
        """Test --filter flag with simple filter"""
        mock_format.return_value = ["AAPL 150C 365DTE ($10.00, 8.5%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--filter", "dte>300"])
        self.assertEqual(result.exit_code, 0)
        # Check that mock was called with a filter_ast (not None)
        call_args = mock_format.call_args
        self.assertIsNotNone(call_args.kwargs["filter_ast"])
        self.assertEqual(call_args.kwargs["filter_ast"]["key"], "dte")
        self.assertEqual(call_args.kwargs["filter_ast"]["op"], ">")
        self.assertEqual(call_args.kwargs["filter_ast"]["value"], 300)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_filter_flag_complex(self, mock_format):
        """Test --filter flag with complex filter (AND)"""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--filter", "dte>10, dte<50"])
        self.assertEqual(result.exit_code, 0)
        # Check that mock was called with a filter_ast
        call_args = mock_format.call_args
        self.assertIsNotNone(call_args.kwargs["filter_ast"])
        self.assertEqual(call_args.kwargs["filter_ast"]["op"], "AND")

    def test_filter_invalid_syntax(self):
        """Test --filter flag with invalid syntax"""
        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--filter", "invalid filter"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Invalid filter expression", result.output)


if __name__ == "__main__":
    unittest.main()
