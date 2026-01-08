"""Tests for advanced input parsing functionality."""
import unittest
from grynn_fplot.core import parse_ticker_input


class TestParseTickerInput(unittest.TestCase):
    """Test the parse_ticker_input function."""

    def test_single_ticker_string(self):
        """Test parsing a single ticker as a string."""
        result = parse_ticker_input("AAPL")
        self.assertEqual(result, ["AAPL"])

    def test_comma_separated_tickers(self):
        """Test parsing comma-separated tickers."""
        result = parse_ticker_input("AAPL,TSLA,MSFT")
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_comma_separated_with_spaces(self):
        """Test parsing comma-separated tickers with spaces."""
        result = parse_ticker_input("AAPL, TSLA, MSFT")
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_space_separated_as_list(self):
        """Test parsing space-separated tickers as a list (from CLI)."""
        result = parse_ticker_input(["AAPL", "TSLA", "MSFT"])
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_division_expression_string(self):
        """Test parsing division expression as a string."""
        result = parse_ticker_input("AAPL/XLK")
        self.assertEqual(result, ["AAPL/XLK"])

    def test_division_expression_list(self):
        """Test parsing division expression in a list."""
        result = parse_ticker_input(["AAPL/XLK"])
        self.assertEqual(result, ["AAPL/XLK"])

    def test_mixed_inputs_list(self):
        """Test parsing mixed inputs (regular tickers and division expressions)."""
        result = parse_ticker_input(["AAPL", "AAPL/XLK", "TW.L"])
        self.assertEqual(result, ["AAPL", "AAPL/XLK", "TW.L"])

    def test_list_with_comma_separated_items(self):
        """Test parsing list where items contain commas."""
        result = parse_ticker_input(["AAPL,TSLA", "MSFT"])
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_quoted_string_with_commas(self):
        """Test parsing quoted string with commas (shell preserves as single string)."""
        result = parse_ticker_input("AAPL, TSLA, MSFT")
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_empty_string(self):
        """Test parsing empty string."""
        result = parse_ticker_input("")
        self.assertEqual(result, [])

    def test_none_input(self):
        """Test parsing None input."""
        result = parse_ticker_input(None)
        self.assertEqual(result, [])

    def test_empty_list(self):
        """Test parsing empty list."""
        result = parse_ticker_input([])
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        """Test parsing whitespace-only string."""
        result = parse_ticker_input("   ")
        self.assertEqual(result, [])

    def test_list_with_whitespace_items(self):
        """Test parsing list with whitespace-only items."""
        result = parse_ticker_input(["AAPL", "  ", "TSLA"])
        self.assertEqual(result, ["AAPL", "TSLA"])

    def test_ticker_with_dots(self):
        """Test parsing ticker with dots (international tickers)."""
        result = parse_ticker_input("TW.L")
        self.assertEqual(result, ["TW.L"])

    def test_multiple_division_expressions(self):
        """Test parsing multiple division expressions."""
        result = parse_ticker_input(["AAPL/XLK", "TSLA/SPY"])
        self.assertEqual(result, ["AAPL/XLK", "TSLA/SPY"])

    def test_mixed_comma_and_space_separated(self):
        """Test parsing mixed comma and space-separated (as list)."""
        result = parse_ticker_input(["AAPL,TSLA", "MSFT", "GOOGL/SPY"])
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT", "GOOGL/SPY"])

    def test_leading_trailing_whitespace(self):
        """Test parsing with leading and trailing whitespace."""
        result = parse_ticker_input("  AAPL, TSLA  ")
        self.assertEqual(result, ["AAPL", "TSLA"])

    def test_extra_commas(self):
        """Test parsing with extra commas."""
        result = parse_ticker_input("AAPL,,TSLA,")
        self.assertEqual(result, ["AAPL", "TSLA"])

    def test_case_preservation(self):
        """Test that ticker case is preserved."""
        result = parse_ticker_input("aapl,TsLa")
        self.assertEqual(result, ["aapl", "TsLa"])


class TestDownloadTickerDataParsing(unittest.TestCase):
    """Test that download_ticker_data handles the new input formats correctly."""

    def test_string_ticker_single(self):
        """Test download_ticker_data with single string ticker (offline test)."""
        from grynn_fplot.core import parse_ticker_input
        
        # Test the parsing part only (don't actually download)
        result = parse_ticker_input("AAPL")
        self.assertEqual(result, ["AAPL"])

    def test_string_ticker_comma_separated(self):
        """Test download_ticker_data with comma-separated string."""
        from grynn_fplot.core import parse_ticker_input
        
        result = parse_ticker_input("AAPL,TSLA")
        self.assertEqual(result, ["AAPL", "TSLA"])

    def test_list_ticker_space_separated(self):
        """Test download_ticker_data with list (space-separated in CLI)."""
        from grynn_fplot.core import parse_ticker_input
        
        result = parse_ticker_input(["AAPL", "TSLA", "MSFT"])
        self.assertEqual(result, ["AAPL", "TSLA", "MSFT"])

    def test_division_expression_parsing(self):
        """Test that division expressions are parsed correctly."""
        from grynn_fplot.core import parse_ticker_input
        
        result = parse_ticker_input(["AAPL/XLK"])
        self.assertEqual(result, ["AAPL/XLK"])

    def test_mixed_input_parsing(self):
        """Test mixed input (regular and division)."""
        from grynn_fplot.core import parse_ticker_input
        
        result = parse_ticker_input(["AAPL", "AAPL/XLK", "TW.L"])
        self.assertEqual(result, ["AAPL", "AAPL/XLK", "TW.L"])


if __name__ == "__main__":
    unittest.main()
