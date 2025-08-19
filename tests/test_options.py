import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from grynn_fplot.core import (
    get_cache_dir,
    calculate_days_to_expiry,
    format_options_for_display,
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
        future_date = (datetime.now().replace(day=1, month=1, year=datetime.now().year + 1)).strftime('%Y-%m-%d')
        dte = calculate_days_to_expiry(future_date)
        self.assertGreater(dte, 0)

        # Test with invalid date format
        dte = calculate_days_to_expiry("invalid-date")
        self.assertEqual(dte, 0)

    @patch('grynn_fplot.core.fetch_options_data')
    def test_format_options_for_display_no_data(self, mock_fetch):
        """Test format_options_for_display when no data is available"""
        mock_fetch.return_value = None
        result = format_options_for_display("AAPL")
        self.assertEqual(result, [])

    @patch('grynn_fplot.core.fetch_options_data')
    def test_format_options_for_display_with_data(self, mock_fetch):
        """Test format_options_for_display with mock data"""
        mock_data = {
            'calls': {
                '2024-12-20': [
                    {'strike': 150.0},
                    {'strike': 155.0},
                ]
            }
        }
        mock_fetch.return_value = mock_data
        
        with patch('grynn_fplot.core.calculate_days_to_expiry', return_value=30):
            result = format_options_for_display("AAPL", "calls")
            self.assertIn("AAPL 150C 30DTE", result)
            self.assertIn("AAPL 155C 30DTE", result)


if __name__ == "__main__":
    unittest.main()