import unittest
from grynn_fplot.filter_parser import (
    parse_filter,
    parse_single_filter,
    parse_time_value,
    parse_value,
    tokenize_filter,
    filter_to_string,
    FilterParseError,
    FilterNode,
)


class TestTimeValueParsing(unittest.TestCase):
    """Test time value parsing functionality"""

    def test_parse_single_day(self):
        """Test parsing single day"""
        self.assertEqual(parse_time_value("1d"), 24.0)
        self.assertEqual(parse_time_value("2d"), 48.0)

    def test_parse_single_hour(self):
        """Test parsing single hour"""
        self.assertEqual(parse_time_value("1h"), 1.0)
        self.assertEqual(parse_time_value("24h"), 24.0)

    def test_parse_decimal_time(self):
        """Test parsing decimal time values"""
        self.assertEqual(parse_time_value("2.5d"), 60.0)  # 2.5 days = 60 hours
        self.assertEqual(parse_time_value("1.5h"), 1.5)  # 1.5 hours

    def test_parse_combined_time(self):
        """Test parsing combined time units"""
        self.assertEqual(parse_time_value("2d15h"), 63.0)  # 48 + 15
        self.assertEqual(parse_time_value("1d12h"), 36.0)  # 24 + 12

    def test_parse_minutes(self):
        """Test parsing minutes"""
        self.assertEqual(parse_time_value("60m"), 1.0)
        self.assertEqual(parse_time_value("30m"), 0.5)

    def test_parse_seconds(self):
        """Test parsing seconds"""
        self.assertEqual(parse_time_value("3600s"), 1.0)

    def test_invalid_time_format(self):
        """Test invalid time formats raise errors"""
        with self.assertRaises(FilterParseError):
            parse_time_value("invalid")
        with self.assertRaises(FilterParseError):
            parse_time_value("123")


class TestValueParsing(unittest.TestCase):
    """Test general value parsing"""

    def test_parse_integer(self):
        """Test parsing integer values"""
        self.assertEqual(parse_value("123"), 123)
        self.assertEqual(parse_value("0"), 0)
        self.assertEqual(parse_value("-5"), -5)

    def test_parse_float(self):
        """Test parsing float values"""
        self.assertEqual(parse_value("123.45"), 123.45)
        self.assertEqual(parse_value("0.5"), 0.5)

    def test_parse_time_values(self):
        """Test parsing time values"""
        self.assertEqual(parse_value("2d15h"), 63.0)
        self.assertEqual(parse_value("1d"), 24.0)

    def test_parse_string(self):
        """Test fallback to string"""
        self.assertEqual(parse_value("text"), "text")
        self.assertEqual(parse_value("abc123xyz"), "abc123xyz")


class TestTokenization(unittest.TestCase):
    """Test filter tokenization"""

    def test_tokenize_simple_filter(self):
        """Test tokenizing simple filter"""
        tokens = tokenize_filter("dte>300")
        self.assertEqual(tokens, ["dte>300"])

    def test_tokenize_and_filters(self):
        """Test tokenizing AND filters"""
        tokens = tokenize_filter("dte>10, dte<15")
        self.assertEqual(tokens, ["dte>10", ",", "dte<15"])

    def test_tokenize_or_filters(self):
        """Test tokenizing OR filters"""
        tokens = tokenize_filter("dte>300 + dte<400")
        self.assertEqual(tokens, ["dte>300", "+", "dte<400"])

    def test_tokenize_with_parentheses(self):
        """Test tokenizing with parentheses"""
        tokens = tokenize_filter("(dte>300 + dte<400), strike>100")
        self.assertEqual(tokens, ["(dte>300 + dte<400)", ",", "strike>100"])

    def test_tokenize_nested_parentheses(self):
        """Test tokenizing nested parentheses"""
        tokens = tokenize_filter("((dte>10 + dte<15), strike>50)")
        self.assertEqual(tokens, ["((dte>10 + dte<15), strike>50)"])

    def test_mismatched_parentheses(self):
        """Test error on mismatched parentheses"""
        with self.assertRaises(FilterParseError):
            tokenize_filter("(dte>10")
        with self.assertRaises(FilterParseError):
            tokenize_filter("dte>10)")


class TestSingleFilterParsing(unittest.TestCase):
    """Test parsing single filter expressions"""

    def test_parse_greater_than(self):
        """Test parsing > operator"""
        node = parse_single_filter("dte>300")
        self.assertEqual(node.key, "dte")
        self.assertEqual(node.operator, ">")
        self.assertEqual(node.value, 300)

    def test_parse_less_than(self):
        """Test parsing < operator"""
        node = parse_single_filter("strike<100")
        self.assertEqual(node.key, "strike")
        self.assertEqual(node.operator, "<")
        self.assertEqual(node.value, 100)

    def test_parse_greater_equal(self):
        """Test parsing >= operator"""
        node = parse_single_filter("volume>=1000")
        self.assertEqual(node.key, "volume")
        self.assertEqual(node.operator, ">=")
        self.assertEqual(node.value, 1000)

    def test_parse_less_equal(self):
        """Test parsing <= operator"""
        node = parse_single_filter("lt_days<=2d15h")
        self.assertEqual(node.key, "lt_days")
        self.assertEqual(node.operator, "<=")
        self.assertEqual(node.value, 63.0)

    def test_parse_equal(self):
        """Test parsing = operator (normalized to ==)"""
        node = parse_single_filter("type=call")
        self.assertEqual(node.key, "type")
        self.assertEqual(node.operator, "==")
        self.assertEqual(node.value, "call")

    def test_parse_not_equal(self):
        """Test parsing != operator"""
        node = parse_single_filter("status!=expired")
        self.assertEqual(node.key, "status")
        self.assertEqual(node.operator, "!=")
        self.assertEqual(node.value, "expired")

    def test_parse_with_spaces(self):
        """Test parsing with spaces"""
        node = parse_single_filter("  dte  >  300  ")
        self.assertEqual(node.key, "dte")
        self.assertEqual(node.operator, ">")
        self.assertEqual(node.value, 300)

    def test_invalid_filter_format(self):
        """Test error on invalid format"""
        with self.assertRaises(FilterParseError):
            parse_single_filter("invalid filter")
        with self.assertRaises(FilterParseError):
            parse_single_filter("dte")
        with self.assertRaises(FilterParseError):
            parse_single_filter(">300")


class TestComplexFilterParsing(unittest.TestCase):
    """Test parsing complex filter expressions"""

    def test_parse_single_filter(self):
        """Test parsing single filter to AST"""
        result = parse_filter("dte>300")
        self.assertEqual(result["key"], "dte")
        self.assertEqual(result["op"], ">")
        self.assertEqual(result["value"], 300)

    def test_parse_and_filters(self):
        """Test parsing AND filters"""
        result = parse_filter("dte>10, dte<15")
        self.assertEqual(result["op"], "AND")
        self.assertEqual(len(result["children"]), 2)
        self.assertEqual(result["children"][0]["key"], "dte")
        self.assertEqual(result["children"][0]["op"], ">")
        self.assertEqual(result["children"][0]["value"], 10)
        self.assertEqual(result["children"][1]["key"], "dte")
        self.assertEqual(result["children"][1]["op"], "<")
        self.assertEqual(result["children"][1]["value"], 15)

    def test_parse_or_filters(self):
        """Test parsing OR filters"""
        result = parse_filter("dte>300 + dte<400")
        self.assertEqual(result["op"], "OR")
        self.assertEqual(len(result["children"]), 2)
        self.assertEqual(result["children"][0]["key"], "dte")
        self.assertEqual(result["children"][0]["op"], ">")
        self.assertEqual(result["children"][1]["key"], "dte")
        self.assertEqual(result["children"][1]["op"], "<")

    def test_parse_mixed_and_or(self):
        """Test parsing mixed AND/OR (AND has higher precedence)"""
        result = parse_filter("(dte>300 + dte<400), strike>100")
        self.assertEqual(result["op"], "AND")
        self.assertEqual(len(result["children"]), 2)
        # First child should be OR
        self.assertEqual(result["children"][0]["op"], "OR")
        # Second child should be simple filter
        self.assertEqual(result["children"][1]["key"], "strike")

    def test_parse_multiple_and_conditions(self):
        """Test parsing multiple AND conditions"""
        result = parse_filter("dte>10, dte<15, strike>100")
        self.assertEqual(result["op"], "AND")
        self.assertEqual(len(result["children"]), 3)

    def test_parse_multiple_or_conditions(self):
        """Test parsing multiple OR conditions"""
        result = parse_filter("dte>300 + dte<400 + strike<50")
        self.assertEqual(result["op"], "OR")
        self.assertEqual(len(result["children"]), 3)

    def test_parse_with_time_values(self):
        """Test parsing with time values"""
        result = parse_filter("lt_days<=2d15h")
        self.assertEqual(result["key"], "lt_days")
        self.assertEqual(result["value"], 63.0)

    def test_parse_complex_nested(self):
        """Test parsing complex nested expression"""
        result = parse_filter("(dte>300 + dte<400), (strike>100, strike<200)")
        self.assertEqual(result["op"], "AND")
        self.assertEqual(len(result["children"]), 2)
        # First child: OR node
        self.assertEqual(result["children"][0]["op"], "OR")
        # Second child: AND node
        self.assertEqual(result["children"][1]["op"], "AND")

    def test_parse_empty_filter(self):
        """Test error on empty filter"""
        with self.assertRaises(FilterParseError):
            parse_filter("")
        with self.assertRaises(FilterParseError):
            parse_filter("   ")

    def test_parse_with_extra_parentheses(self):
        """Test parsing with extra wrapping parentheses"""
        result = parse_filter("(dte>300)")
        self.assertEqual(result["key"], "dte")
        self.assertEqual(result["op"], ">")
        self.assertEqual(result["value"], 300)


class TestFilterToString(unittest.TestCase):
    """Test converting filter AST back to string"""

    def test_simple_filter_to_string(self):
        """Test converting simple filter to string"""
        filter_dict = {"key": "dte", "op": ">", "value": 300}
        result = filter_to_string(filter_dict)
        self.assertEqual(result, "dte>300")

    def test_and_filters_to_string(self):
        """Test converting AND filters to string"""
        filter_dict = {
            "op": "AND",
            "children": [{"key": "dte", "op": ">", "value": 10}, {"key": "dte", "op": "<", "value": 15}],
        }
        result = filter_to_string(filter_dict)
        self.assertEqual(result, "(dte>10, dte<15)")

    def test_or_filters_to_string(self):
        """Test converting OR filters to string"""
        filter_dict = {
            "op": "OR",
            "children": [{"key": "dte", "op": ">", "value": 300}, {"key": "dte", "op": "<", "value": 400}],
        }
        result = filter_to_string(filter_dict)
        self.assertEqual(result, "(dte>300 + dte<400)")

    def test_nested_filters_to_string(self):
        """Test converting nested filters to string"""
        filter_dict = {
            "op": "AND",
            "children": [
                {"op": "OR", "children": [{"key": "dte", "op": ">", "value": 300}, {"key": "dte", "op": "<", "value": 400}]},
                {"key": "strike", "op": ">", "value": 100},
            ],
        }
        result = filter_to_string(filter_dict)
        self.assertEqual(result, "((dte>300 + dte<400), strike>100)")


class TestFilterNodeDataclass(unittest.TestCase):
    """Test FilterNode dataclass"""

    def test_filter_node_creation(self):
        """Test creating FilterNode"""
        node = FilterNode(key="dte", operator=">", value=300)
        self.assertEqual(node.key, "dte")
        self.assertEqual(node.operator, ">")
        self.assertEqual(node.value, 300)

    def test_filter_node_to_dict(self):
        """Test FilterNode to_dict"""
        node = FilterNode(key="strike", operator="<=", value=100.5)
        result = node.to_dict()
        self.assertEqual(result, {"key": "strike", "op": "<=", "value": 100.5})


if __name__ == "__main__":
    unittest.main()
