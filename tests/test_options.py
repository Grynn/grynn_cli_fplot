import unittest
from unittest.mock import patch
from datetime import datetime
from grynn_fplot.core import (
    get_cache_dir,
    calculate_days_to_expiry,
    format_options_for_display,
    parse_time_expression,
    filter_expiry_dates,
    calculate_cagr_to_breakeven,
    calculate_put_annualized_return,
)


class TestOptionsCore(unittest.TestCase):
    def test_get_cache_dir(self):
        """Test that cache directory is created and returned"""
        cache_dir = get_cache_dir()
        self.assertTrue(cache_dir.exists())
        self.assertEqual(cache_dir.name, "grynn_fplot")

    def test_calculate_days_to_expiry(self):
        """Test calculation of days to expiry"""
        # Test with a future date
        future_date = (datetime.now().replace(day=1, month=1, year=datetime.now().year + 1)).strftime("%Y-%m-%d")
        dte = calculate_days_to_expiry(future_date)
        self.assertGreater(dte, 0)

        # Test with invalid date format
        dte = calculate_days_to_expiry("invalid-date")
        self.assertEqual(dte, 0)

    @patch("grynn_fplot.core.fetch_options_data")
    def test_format_options_for_display_no_data(self, mock_fetch):
        """Test format_options_for_display when no data is available"""
        mock_fetch.return_value = None
        result = format_options_for_display("AAPL")
        self.assertEqual(result, [])

    @patch("grynn_fplot.core.fetch_options_data")
    @patch("grynn_fplot.core.get_spot_price")
    def test_format_options_for_display_with_data(self, mock_spot_price, mock_fetch):
        """Test format_options_for_display with mock data"""
        from datetime import datetime, timedelta

        # Use a future date that won't expire
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        mock_spot_price.return_value = 150.0
        mock_data = {
            "expiry_dates": [future_date],
            "calls": {
                future_date: [
                    {"strike": 150.0, "lastPrice": 5.0, "volume": 100, "lastTradeDate": None},
                    {"strike": 155.0, "lastPrice": 3.0, "volume": 50, "lastTradeDate": None},
                ]
            },
        }
        mock_fetch.return_value = mock_data

        with patch("grynn_fplot.core.calculate_days_to_expiry", return_value=30):
            result = format_options_for_display("AAPL", "calls")
            self.assertTrue(any("AAPL 150C 30DTE ($5.00," in item for item in result))
            self.assertTrue(any("AAPL 155C 30DTE ($3.00," in item for item in result))

    def test_parse_time_expression(self):
        """Test parsing of time expressions"""
        self.assertEqual(parse_time_expression("3m"), 90)
        self.assertEqual(parse_time_expression("6m"), 180)
        self.assertEqual(parse_time_expression("1y"), 365)
        self.assertEqual(parse_time_expression("2w"), 14)
        self.assertEqual(parse_time_expression("30d"), 30)
        self.assertEqual(parse_time_expression("invalid"), 180)  # Default fallback

    def test_filter_expiry_dates(self):
        """Test filtering of expiry dates"""
        # Create test dates - some within range, some beyond
        from datetime import timedelta

        current_date = datetime.now()

        near_date = (current_date + timedelta(days=30)).strftime("%Y-%m-%d")
        mid_date = (current_date + timedelta(days=100)).strftime("%Y-%m-%d")
        far_date = (current_date + timedelta(days=200)).strftime("%Y-%m-%d")

        expiry_dates = [near_date, mid_date, far_date]

        # Test 90-day filter
        filtered = filter_expiry_dates(expiry_dates, 90, False)
        self.assertIn(near_date, filtered)
        self.assertNotIn(far_date, filtered)

        # Test show_all flag
        all_dates = filter_expiry_dates(expiry_dates, 90, True)
        self.assertEqual(len(all_dates), 3)

    def test_calculate_cagr_to_breakeven(self):
        """Test CAGR to breakeven calculation for calls"""
        spot_price = 150.0
        strike = 155.0
        option_price = 3.0
        dte = 30

        cagr = calculate_cagr_to_breakeven(spot_price, strike, option_price, dte)
        self.assertGreater(cagr, 0)

        # Test edge cases
        self.assertEqual(calculate_cagr_to_breakeven(0, 100, 5, 30), 0.0)
        self.assertEqual(calculate_cagr_to_breakeven(100, 110, 0, 30), 0.0)
        self.assertEqual(calculate_cagr_to_breakeven(100, 110, 5, 0), 0.0)

    def test_calculate_put_annualized_return(self):
        """Test annualized return calculation for puts"""
        strike_price = 145.0
        option_price = 3.0
        dte = 30

        # premium / (strike - premium) * 365 / dte = 3 / 142 * 365 / 30 = 0.2570...
        annual_return = calculate_put_annualized_return(strike_price, option_price, dte)
        expected = (3.0 / (145.0 - 3.0)) * 365 / 30
        self.assertAlmostEqual(annual_return, expected, places=6)

        # Test edge cases
        self.assertEqual(calculate_put_annualized_return(145, 0, 30), 0.0)
        self.assertEqual(calculate_put_annualized_return(145, 5, 0), 0.0)
        self.assertEqual(calculate_put_annualized_return(145, 200, 30), 0.0)  # premium > strike


if __name__ == "__main__":
    unittest.main()
