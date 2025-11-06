import unittest
from grynn_fplot.core import evaluate_filter


class TestEvaluateFilter(unittest.TestCase):
    """Test filter evaluation against data"""

    def test_simple_greater_than(self):
        """Test simple > filter"""
        filter_ast = {"key": "dte", "op": ">", "value": 30}
        data = {"dte": 50}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"dte": 20}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_simple_less_than(self):
        """Test simple < filter"""
        filter_ast = {"key": "strike", "op": "<", "value": 100}
        data = {"strike": 90}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"strike": 110}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_greater_equal(self):
        """Test >= filter"""
        filter_ast = {"key": "volume", "op": ">=", "value": 100}
        data = {"volume": 100}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"volume": 150}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"volume": 50}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_less_equal(self):
        """Test <= filter"""
        filter_ast = {"key": "price", "op": "<=", "value": 5.0}
        data = {"price": 5.0}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"price": 3.0}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"price": 7.0}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_equal(self):
        """Test == filter"""
        filter_ast = {"key": "type", "op": "==", "value": "call"}
        data = {"type": "call"}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"type": "put"}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_not_equal(self):
        """Test != filter"""
        filter_ast = {"key": "status", "op": "!=", "value": "expired"}
        data = {"status": "active"}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"status": "expired"}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_missing_key(self):
        """Test filter with missing key in data"""
        filter_ast = {"key": "missing", "op": ">", "value": 10}
        data = {"dte": 30}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_and_filter(self):
        """Test AND logical filter"""
        filter_ast = {
            "op": "AND",
            "children": [{"key": "dte", "op": ">", "value": 10}, {"key": "dte", "op": "<", "value": 50}],
        }
        data = {"dte": 30}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"dte": 5}
        self.assertFalse(evaluate_filter(filter_ast, data))

        data = {"dte": 60}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_or_filter(self):
        """Test OR logical filter"""
        filter_ast = {
            "op": "OR",
            "children": [{"key": "dte", "op": "<", "value": 10}, {"key": "dte", "op": ">", "value": 300}],
        }
        data = {"dte": 5}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"dte": 350}
        self.assertTrue(evaluate_filter(filter_ast, data))

        data = {"dte": 50}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_nested_filters(self):
        """Test nested AND/OR filters"""
        filter_ast = {
            "op": "AND",
            "children": [
                {
                    "op": "OR",
                    "children": [{"key": "dte", "op": ">", "value": 300}, {"key": "dte", "op": "<", "value": 30}],
                },
                {"key": "strike", "op": ">", "value": 100},
            ],
        }

        # dte=350, strike=150: (350>300 OR 350<30) AND 150>100 = True AND True = True
        data = {"dte": 350, "strike": 150}
        self.assertTrue(evaluate_filter(filter_ast, data))

        # dte=20, strike=150: (20>300 OR 20<30) AND 150>100 = True AND True = True
        data = {"dte": 20, "strike": 150}
        self.assertTrue(evaluate_filter(filter_ast, data))

        # dte=50, strike=150: (50>300 OR 50<30) AND 150>100 = False AND True = False
        data = {"dte": 50, "strike": 150}
        self.assertFalse(evaluate_filter(filter_ast, data))

        # dte=350, strike=50: (350>300 OR 350<30) AND 50>100 = True AND False = False
        data = {"dte": 350, "strike": 50}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_invalid_operator(self):
        """Test invalid operator returns False"""
        filter_ast = {"key": "dte", "op": "~=", "value": 30}
        data = {"dte": 30}
        self.assertFalse(evaluate_filter(filter_ast, data))

    def test_none_value_handling(self):
        """Test handling of None values in data"""
        # None should not match any comparison except != None
        filter_ast = {"key": "return", "op": ">", "value": 0}
        data = {"return": None}
        self.assertFalse(evaluate_filter(filter_ast, data))

        # None with >= operator
        filter_ast = {"key": "return", "op": ">=", "value": 0}
        data = {"return": None}
        self.assertFalse(evaluate_filter(filter_ast, data))

        # None with == operator
        filter_ast = {"key": "return", "op": "==", "value": None}
        data = {"return": None}
        self.assertTrue(evaluate_filter(filter_ast, data))

        # None with != operator
        filter_ast = {"key": "return", "op": "!=", "value": None}
        data = {"return": None}
        self.assertFalse(evaluate_filter(filter_ast, data))

        # Non-None with != operator
        filter_ast = {"key": "return", "op": "!=", "value": None}
        data = {"return": 0.5}
        self.assertTrue(evaluate_filter(filter_ast, data))

    def test_invalid_logical_operator(self):
        """Test invalid logical operator returns False"""
        filter_ast = {"op": "XOR", "children": [{"key": "dte", "op": ">", "value": 10}]}
        data = {"dte": 30}
        self.assertFalse(evaluate_filter(filter_ast, data))


if __name__ == "__main__":
    unittest.main()
