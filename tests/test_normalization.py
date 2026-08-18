"""Tests for price normalization with staggered ticker histories."""

import unittest

import pandas as pd

from grynn_fplot.cli import _normalize_frame_to_visible_window, _normalize_ohlcv_to_visible_window
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

    def test_visible_window_normalization_rebases_to_current_view(self):
        """Interactive comparative charts should rebase after pan or zoom."""
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        df = pd.DataFrame(
            {
                "A": [100.0, 80.0, 120.0, 90.0],
                "B": [None, 40.0, 80.0, 100.0],
            },
            index=dates,
        )

        visible_mask = [False, False, True, True]
        normalized, drawdown = _normalize_frame_to_visible_window(df, visible_mask)

        self.assertAlmostEqual(normalized.loc[dates[2], "A"], 100.0)
        self.assertAlmostEqual(normalized.loc[dates[2], "B"], 100.0)
        self.assertAlmostEqual(normalized.loc[dates[3], "A"], 75.0)
        self.assertAlmostEqual(normalized.loc[dates[3], "B"], 125.0)
        self.assertTrue(pd.isna(drawdown.loc[dates[1], "A"]))
        self.assertAlmostEqual(drawdown.loc[dates[2], "A"], 0.0)
        self.assertAlmostEqual(drawdown.loc[dates[3], "A"], -0.25)

    def test_candlestick_prices_share_first_visible_close_as_base(self):
        """OHLC geometry should be retained while volume remains untouched."""
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        df = pd.DataFrame(
            {
                "Open": [40.0, 48.0, 55.0],
                "High": [44.0, 55.0, 66.0],
                "Low": [36.0, 45.0, 50.0],
                "Close": [42.0, 50.0, 60.0],
                "Volume": [1_000, 2_000, 3_000],
            },
            index=dates,
        )

        result = _normalize_ohlcv_to_visible_window(df, view_start_idx=1)

        self.assertEqual(result.loc[dates[1], "Close"], 100.0)
        self.assertEqual(result.loc[dates[1], "Open"], 96.0)
        self.assertEqual(result.loc[dates[2], "High"], 132.0)
        self.assertEqual(result.loc[dates[2], "Low"], 100.0)
        self.assertListEqual(result["Volume"].tolist(), df["Volume"].tolist())
        self.assertEqual(df.loc[dates[1], "Close"], 50.0)


if __name__ == "__main__":
    unittest.main()
