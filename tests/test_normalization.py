"""Tests for price normalization with staggered ticker histories."""

import unittest

import pandas as pd

from grynn_fplot.core import normalize_prices


class TestNormalizePrices(unittest.TestCase):
    """Regression tests for normalized multi-ticker charts."""

    def test_dataframe_uses_first_valid_value_per_column(self):
        """Late-listed tickers should normalize from their own first valid price."""
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        df = pd.DataFrame(
            {
                "OLDER": [10.0, 12.0, 15.0, 20.0],
                "NEWER": [None, None, 50.0, 75.0],
            },
            index=dates,
        )

        result = normalize_prices(df)

        self.assertEqual(result.loc[dates[0], "OLDER"], 100.0)
        self.assertTrue(pd.isna(result.loc[dates[0], "NEWER"]))
        self.assertTrue(pd.isna(result.loc[dates[1], "NEWER"]))
        self.assertEqual(result.loc[dates[2], "NEWER"], 100.0)
        self.assertEqual(result.loc[dates[3], "NEWER"], 150.0)

    def test_series_uses_first_valid_value(self):
        """Series normalization should also tolerate leading NaNs."""
        series = pd.Series([None, 25.0, 30.0], index=pd.date_range("2024-01-01", periods=3, freq="D"))

        result = normalize_prices(series)

        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertEqual(result.iloc[1], 100.0)
        self.assertEqual(result.iloc[2], 120.0)


if __name__ == "__main__":
    unittest.main()
