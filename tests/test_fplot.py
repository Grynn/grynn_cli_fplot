import unittest
from datetime import datetime
from grynn_fplot.core import parse_start_date


class TestParseDate(unittest.TestCase):
    def test_none_date(self):
        self.assertIsInstance(parse_start_date(None), datetime)

    def test_ytd_date(self):
        result = parse_start_date("YTD")
        self.assertEqual(result, datetime(datetime.now().year, 1, 1))

    def test_last_3_months(self):
        test_strings = [
            "last 3 months",
            "last 3 mos",
            "last 3mo",
            "3mths",
            "3m ago",
            "3m",
        ]
        r1 = parse_start_date("last 3 months")
        for test_string in test_strings:
            result = parse_start_date(test_string)
            self.assertIsInstance(result, datetime)
            self.assertEqual(result.date(), r1.date())

    def test_last_10_days(self):
        result = parse_start_date("last 10 days")
        self.assertIsInstance(result, datetime)

    def test_last_2_years(self):
        result = parse_start_date("last 2 yrs")
        self.assertIsInstance(result, datetime)

    def test_2_yrs_ago(self):
        result = parse_start_date("2 yrs ago")
        self.assertIsInstance(result, datetime)

        result = parse_start_date("2yrs ago")
        self.assertIsInstance(result, datetime)

    def test_last_4_weeks(self):
        result = parse_start_date("last 4 weeks")
        self.assertIsInstance(result, datetime)

    def test_invalid_unit(self):
        with self.assertRaises(ValueError):
            parse_start_date("last 5 xyz")

    def test_datetime_object(self):
        date = datetime(2020, 1, 1)
        self.assertEqual(parse_start_date(date), date)

    def test_invalid_type(self):
        with self.assertRaises(ValueError):
            parse_start_date(12345)

        with self.assertRaises(ValueError):
            parse_start_date("junk week")

        with self.assertRaises(ValueError):
            parse_start_date("invalid date")


if __name__ == "__main__":
    unittest.main()
