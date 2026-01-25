"""Integration tests for CLI argument parsing."""
import unittest
from unittest.mock import patch
from click.testing import CliRunner
from grynn_fplot.cli import display_plot
import pandas as pd
from datetime import datetime, timedelta


class TestCLIArgumentParsing(unittest.TestCase):
    """Test CLI argument parsing for various input formats."""

    def setUp(self):
        self.runner = CliRunner()
        
    def _create_mock_df(self, columns):
        """Create a mock DataFrame with proper DatetimeIndex."""
        dates = pd.date_range(start=datetime.now() - timedelta(days=2), periods=3, freq='D')
        data = {col: [100, 101, 102] for col in columns}
        df = pd.DataFrame(data, index=dates)
        return df

    def test_version_flag_still_works(self):
        """Test that version flag still works."""
        result = self.runner.invoke(display_plot, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("fplot", result.output)

    def test_missing_ticker_shows_help(self):
        """Test that missing ticker shows helpful error message."""
        result = self.runner.invoke(display_plot, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)
        self.assertIn("Examples:", result.output)

    @patch("grynn_fplot.cli.download_ohlcv_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_single_ticker(self, mock_show, mock_download_ohlcv):
        """Test single ticker argument - should use candlestick chart."""
        # Create OHLCV data for single ticker (3 years since we always fetch 3 years)
        dates = pd.date_range(start=datetime.now() - timedelta(days=1095), periods=1095, freq='D')
        data = {
            'Open': [100 + i * 0.1 for i in range(1095)],
            'High': [101 + i * 0.1 for i in range(1095)],
            'Low': [99 + i * 0.1 for i in range(1095)],
            'Close': [100.5 + i * 0.1 for i in range(1095)],
            'Volume': [1000000 + i * 1000 for i in range(1095)]
        }
        mock_df = pd.DataFrame(data, index=dates)
        mock_download_ohlcv.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL"])
        self.assertEqual(result.exit_code, 0)
        mock_download_ohlcv.assert_called_once()

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_space_separated_tickers(self, mock_show, mock_download):
        """Test space-separated tickers."""
        mock_df = self._create_mock_df(["AAPL", "TSLA", "MSFT"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL", "TSLA", "MSFT"])
        self.assertEqual(result.exit_code, 0)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_comma_separated_tickers(self, mock_show, mock_download):
        """Test comma-separated tickers."""
        mock_df = self._create_mock_df(["AAPL", "TSLA"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL,TSLA"])
        self.assertEqual(result.exit_code, 0)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_division_expression(self, mock_show, mock_download):
        """Test division expression."""
        mock_df = self._create_mock_df(["AAPL", "XLK", "AAPL/XLK"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL/XLK"])
        self.assertEqual(result.exit_code, 0)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_mixed_inputs(self, mock_show, mock_download):
        """Test mixed inputs (regular and division)."""
        mock_df = self._create_mock_df(["AAPL", "XLK", "TW.L", "AAPL/XLK"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL", "AAPL/XLK", "TW.L"])
        self.assertEqual(result.exit_code, 0)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_options_with_single_ticker(self, mock_format):
        """Test --call flag works with new argument parsing."""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)"]

        result = self.runner.invoke(display_plot, ["AAPL", "--call"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AAPL 150C 30DTE", result.output)

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_options_with_multiple_tickers_uses_first(self, mock_format):
        """Test --call flag with multiple tickers uses first one."""
        mock_format.return_value = ["AAPL 150C 30DTE ($5.00, 15.2%)"]

        # Multiple tickers provided, but only first should be used for options
        result = self.runner.invoke(display_plot, ["AAPL", "TSLA", "--call"])
        self.assertEqual(result.exit_code, 0)
        # Check that format_options_for_display was called with "AAPL"
        call_args = mock_format.call_args[0]
        self.assertEqual(call_args[0], "AAPL")


if __name__ == "__main__":
    unittest.main()
