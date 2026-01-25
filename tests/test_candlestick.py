"""Tests for candlestick chart functionality."""
import unittest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from grynn_fplot.cli import display_plot
import pandas as pd
from datetime import datetime, timedelta


class TestCandlestickChart(unittest.TestCase):
    """Test candlestick chart functionality."""

    def setUp(self):
        self.runner = CliRunner()

    def _create_ohlcv_df(self, days=1095):
        """Create a mock OHLCV DataFrame. Default is 3 years (1095 days)."""
        dates = pd.date_range(start=datetime.now() - timedelta(days=days), periods=days, freq='D')
        data = {
            'Open': [100 + i * 0.1 for i in range(days)],
            'High': [101 + i * 0.1 for i in range(days)],
            'Low': [99 + i * 0.1 for i in range(days)],
            'Close': [100.5 + i * 0.1 for i in range(days)],
            'Volume': [1000000 + i * 1000 for i in range(days)]
        }
        return pd.DataFrame(data, index=dates)

    def _create_multi_ticker_df(self, columns):
        """Create a mock DataFrame for multi-ticker comparison."""
        dates = pd.date_range(start=datetime.now() - timedelta(days=2), periods=3, freq='D')
        data = {col: [100, 101, 102] for col in columns}
        return pd.DataFrame(data, index=dates)

    @patch("grynn_fplot.cli.download_ohlcv_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_single_ticker_uses_candlestick(self, mock_show, mock_download_ohlcv):
        """Test that single ticker uses candlestick chart."""
        mock_df = self._create_ohlcv_df(days=1095)  # 3 years of data
        mock_download_ohlcv.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL"])
        self.assertEqual(result.exit_code, 0)
        # Verify candlestick function was called (download_ohlcv_data)
        mock_download_ohlcv.assert_called_once()
        self.assertIn("candlestick", result.output.lower())

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_multi_ticker_uses_line_chart(self, mock_show, mock_download):
        """Test that multi-ticker uses traditional line chart."""
        mock_df = self._create_multi_ticker_df(["AAPL", "MSFT", "GOOGL"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL", "MSFT", "GOOGL"])
        self.assertEqual(result.exit_code, 0)
        # Verify multi-ticker function was called (download_ticker_data)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.download_ticker_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_division_uses_line_chart(self, mock_show, mock_download):
        """Test that division operations use line chart."""
        mock_df = self._create_multi_ticker_df(["AAPL", "XLK", "AAPL/XLK"])
        mock_download.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL/XLK"])
        self.assertEqual(result.exit_code, 0)
        # Verify multi-ticker function was called (download_ticker_data)
        mock_download.assert_called_once()

    @patch("grynn_fplot.cli.download_ohlcv_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_candlestick_with_sma_data(self, mock_show, mock_download_ohlcv):
        """Test candlestick with sufficient data for SMAs."""
        # Create data with 1095 days (3 years) to ensure SMAs can be calculated
        mock_df = self._create_ohlcv_df(days=1095)
        mock_download_ohlcv.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL", "--since", "1y"])
        self.assertEqual(result.exit_code, 0)
        mock_download_ohlcv.assert_called_once()

    @patch("grynn_fplot.cli.download_ohlcv_data")
    @patch("grynn_fplot.cli.plt.show")
    def test_candlestick_with_limited_display_window(self, mock_show, mock_download_ohlcv):
        """Test candlestick with short display window but full data fetch."""
        # Create data with 3 years but only display 3 months
        mock_df = self._create_ohlcv_df(days=1095)
        mock_download_ohlcv.return_value = mock_df

        result = self.runner.invoke(display_plot, ["AAPL", "--since", "3m"])
        self.assertEqual(result.exit_code, 0)
        mock_download_ohlcv.assert_called_once()


class TestDownloadOHLCVData(unittest.TestCase):
    """Test the download_ohlcv_data function."""

    @patch("grynn_fplot.core.yfinance.Ticker")
    def test_download_ohlcv_data(self, mock_ticker_class):
        """Test that download_ohlcv_data returns proper OHLCV columns."""
        from grynn_fplot.core import download_ohlcv_data
        from datetime import datetime

        # Create mock data
        dates = pd.date_range(start=datetime.now() - timedelta(days=10), periods=10, freq='D')
        mock_data = pd.DataFrame({
            'Open': [100] * 10,
            'High': [101] * 10,
            'Low': [99] * 10,
            'Close': [100.5] * 10,
            'Volume': [1000000] * 10,
            'Dividends': [0] * 10,  # Extra column that should not be returned
            'Stock Splits': [0] * 10  # Extra column that should not be returned
        }, index=dates)

        # Mock the Ticker instance
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_data
        mock_ticker_class.return_value = mock_ticker_instance

        # Call the function
        result = download_ohlcv_data("AAPL", datetime.now() - timedelta(days=10), "1d")

        # Verify result
        self.assertIsInstance(result, pd.DataFrame)
        self.assertListEqual(list(result.columns), ['Open', 'High', 'Low', 'Close', 'Volume'])
        self.assertEqual(len(result), 10)

    def test_download_ohlcv_data_requires_yfinance(self):
        """Test that download_ohlcv_data raises ImportError if yfinance not available."""
        from grynn_fplot.core import download_ohlcv_data
        from datetime import datetime

        # Patch yfinance to None to simulate missing package
        with patch("grynn_fplot.core.yfinance", None):
            with self.assertRaises(ImportError) as context:
                download_ohlcv_data("AAPL", datetime.now() - timedelta(days=10), "1d")
            self.assertIn("yfinance", str(context.exception))


if __name__ == "__main__":
    unittest.main()
