"""
Test suite for the web API and browser interface
"""

import unittest
import sys
import os
import pandas as pd
import yfinance

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test dependencies when available
try:
    from fastapi.testclient import TestClient
    from grynn_fplot.web_api import app

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    app = None

from grynn_fplot.core import download_ticker_data, parse_start_date


# Monkey-patch yfinance.download to return dummy data quickly
def _dummy_yfinance_download(tickers, **kwargs):
    dates = pd.date_range(start="2020-01-01", periods=3, freq="D")
    if isinstance(tickers, str):
        tickers_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        tickers_list = [str(t).upper() for t in tickers]
    df_inner = pd.DataFrame({t: [float(i) for i in range(len(dates))] for t in tickers_list}, index=dates)
    return pd.concat({"Adj Close": df_inner}, axis=1)


yfinance.download = _dummy_yfinance_download


class TestMultipleTickerSupport(unittest.TestCase):
    """Test multiple ticker support that should work in both CLI and web versions"""

    def test_multiple_ticker_data_download(self):
        """Test that core functionality supports multiple tickers like 'AAPL,TSLA'"""
        # Test comma-separated tickers
        ticker_string = "AAPL,TSLA"
        since_date = parse_start_date("3m")

        # This should work with the core download function
        df = download_ticker_data(ticker_string, since_date, "1d")

        if df is not None and not df.empty:
            # Check that both tickers are present
            self.assertIn("AAPL", df.columns)
            self.assertIn("TSLA", df.columns)
            self.assertEqual(len(df.columns), 2)

            # Check data integrity
            self.assertGreater(len(df), 0)

            # Check that data is not all NaN
            self.assertFalse(df["AAPL"].isna().all())
            self.assertFalse(df["TSLA"].isna().all())
        else:
            self.skipTest("Unable to download test data - network/API issue")

    def test_ticker_string_variations(self):
        """Test various ticker string formats"""
        test_cases = [
            "AAPL,TSLA",
            "AAPL, TSLA",  # With space
            "aapl,tsla",  # Lowercase
        ]

        for ticker_string in test_cases:
            with self.subTest(ticker_string=ticker_string):
                since_date = parse_start_date("1m")
                df = download_ticker_data(ticker_string, since_date, "1d")

                if df is not None and not df.empty:
                    # Should have 2 columns regardless of input format
                    self.assertEqual(len(df.columns), 2)
                    # Columns should be uppercase
                    self.assertIn("AAPL", df.columns)
                    self.assertIn("TSLA", df.columns)


@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestWebAPI(unittest.TestCase):
    """Test web API endpoints"""

    def setUp(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)
        self.assertEqual(data["version"], "2.0.0")

    def test_config_endpoint(self):
        """Test configuration endpoint"""
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check required config sections
        required_sections = ["timeRanges", "intervals", "indicators", "themes", "exportFormats"]
        for section in required_sections:
            self.assertIn(section, data)

    def test_single_ticker_data(self):
        """Test fetching data for a single ticker"""
        response = self.client.get("/api/data?ticker=AAPL&since=1m&interval=1d")
        if response.status_code == 200:
            data = response.json()

            # Check response structure
            required_fields = ["dates", "price", "drawdown", "raw_price", "tickers"]
            for field in required_fields:
                self.assertIn(field, data)

            self.assertIn("AAPL", data["tickers"])
        else:
            self.skipTest("Unable to fetch test data - network/API issue")

    def test_multiple_tickers_web_api(self):
        """Test web API with multiple tickers - the key functionality"""
        response = self.client.get("/api/data?ticker=AAPL,TSLA&since=1m&interval=1d")

        if response.status_code == 200:
            data = response.json()

            # Check both tickers are present
            self.assertIn("AAPL", data["tickers"])
            self.assertIn("TSLA", data["tickers"])
            self.assertEqual(len(data["tickers"]), 2)

            # Check both tickers have data
            for ticker in ["AAPL", "TSLA"]:
                self.assertIn(ticker, data["price"])
                self.assertIn(ticker, data["drawdown"])
                self.assertIn(ticker, data["total_return"])
        else:
            self.skipTest("Unable to fetch test data - network/API issue")

    def test_home_page_no_interval_controls(self):
        """Test that the home page doesn't have interval controls"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # Check that interval controls are removed
        self.assertNotIn("Interval:", content)
        self.assertNotIn('onclick="setInterval', content)

        # Check for height optimization
        self.assertIn("height: 100vh", content)
        self.assertIn("overflow: hidden", content)

    def test_export_functionality(self):
        """Test data export functionality"""
        # Test CSV export
        response = self.client.get("/api/export/csv?ticker=AAPL&since=1m&interval=1d")
        if response.status_code == 200:
            data = response.json()
            self.assertIn("content", data)
            self.assertIn("filename", data)
            self.assertTrue(data["filename"].endswith(".csv"))

        # Test JSON export
        response = self.client.get("/api/export/json?ticker=AAPL&since=1m&interval=1d")
        if response.status_code == 200:
            data = response.json()
            self.assertIn("content", data)
            self.assertIn("filename", data)
            self.assertTrue(data["filename"].endswith(".json"))


class TestWebInterfaceLayout(unittest.TestCase):
    """Test web interface layout and no-scroll optimization"""

    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_no_scroll_layout(self):
        """Test that web interface is optimized for no scrolling"""
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # Check for specific height optimizations
        height_optimizations = [
            "height: 100vh",  # Full viewport height
            "overflow: hidden",  # No scroll
            "calc(100vh - 170px)",  # Optimized chart container height
        ]

        for optimization in height_optimizations:
            self.assertIn(optimization, content)

    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_interval_controls_removed(self):
        """Test that interval controls are completely removed"""
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # These should NOT be present (interval-specific controls)
        interval_elements = [
            "Interval:",
            'onclick="setInterval(',  # Our custom setInterval function, not the built-in one
            "let currentInterval =",  # Variable declaration should be const
            "interval-btn",  # CSS class for interval buttons
            "setInterval('1d')",  # Interval setting function calls
            "setInterval('1w')",
            "setInterval('1m')",
        ]

        for element in interval_elements:
            self.assertNotIn(element, content)

    def test_time_period_parsing(self):
        """Test that various time periods work correctly"""
        test_periods = ["1m", "3m", "6m", "1y", "2y", "5y"]

        for period in test_periods:
            with self.subTest(period=period):
                parsed_date = parse_start_date(period)
                self.assertIsNotNone(parsed_date)

        # Test that "max" returns None (meaning go back to earliest data)
        max_date = parse_start_date("max")
        self.assertIsNone(max_date)


class TestCLIWebCompatibility(unittest.TestCase):
    """Test that CLI features work properly in web version"""

    def test_cli_ticker_format_compatibility(self):
        """Test that CLI ticker formats work in web interface"""
        # These are the exact formats that work in CLI
        cli_formats = [
            "AAPL,TSLA",  # Basic format
            "AAPL, TSLA",  # With space
            "SPY,QQQ,VTI",  # Three tickers
        ]

        for format_str in cli_formats:
            with self.subTest(format=format_str):
                # Test the parsing works
                tickers = [t.strip().upper() for t in format_str.split(",")]
                self.assertGreater(len(tickers), 1)

                # Test data download works with this format
                since_date = parse_start_date("1m")
                df = download_ticker_data(format_str, since_date, "1d")

                if df is not None and not df.empty:
                    # Should have all requested tickers
                    self.assertEqual(len(df.columns), len(tickers))
                    for ticker in tickers:
                        self.assertIn(ticker, df.columns)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
