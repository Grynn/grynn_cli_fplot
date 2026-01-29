"""Filter parser for options filtering with AST-style output.

This module provides parsing and evaluation of filter expressions for options data.
Filters support logical operators (AND/OR) and comparison operators.

Syntax:
- Comma (`,`) represents AND operation
- Plus (`+`) represents OR operation
- Comparison operators: `>`, `<`, `>=`, `<=`, `=`, `!=`
- Parentheses for grouping: `(expr1 + expr2), expr3`

Examples:
- "dte>300" - Single condition
- "dte>10, dte<15" - Multiple AND conditions (10 < dte < 15)
- "dte>300 + dte<400" - OR conditions (dte > 300 OR dte < 400)
- "(dte>300 + dte<400), strike>100" - Nested: (dte>300 OR dte<400) AND strike>100

Output Format:
- AST with nodes representing filters and logical operations
- Each filter node: {"key": str, "op": str, "value": Any}
- Logical nodes: {"op": "AND"|"OR", "children": [nodes]}
"""

import re
from typing import Any, Dict, List, Union
from dataclasses import dataclass


# Registry of available filter fields with descriptions
FILTER_FIELDS = {
    "dte": {"description": "Days to expiry", "type": "integer", "example": "dte>150"},
    "volume": {"description": "Option trading volume", "type": "integer", "example": "volume>100"},
    "price": {"description": "Last traded price", "type": "float", "example": "price<5.0"},
    "return": {
        "description": "Return metric (CAGR for calls, annualized return for puts)",
        "type": "float",
        "aliases": ["ret", "ar"],
        "example": "return>0.15",
    },
    "ret": {"description": "Alias for 'return'", "type": "float", "alias_of": "return", "example": "ret>0.15"},
    "ar": {
        "description": "Alias for 'return' (annualized return)",
        "type": "float",
        "alias_of": "return",
        "example": "ar>0.15",
    },
    "strike_pct": {
        "description": "Strike percentage relative to spot price (positive = above spot, negative = below spot)",
        "type": "float",
        "aliases": ["sp"],
        "example": "strike_pct>5",
    },
    "sp": {"description": "Alias for 'strike_pct'", "type": "float", "alias_of": "strike_pct", "example": "sp>5"},
    "lt_days": {
        "description": "Days since last trade (useful for filtering stale/illiquid options)",
        "type": "integer",
        "example": "lt_days<7",
    },
    "leverage": {
        "description": "Implied leverage (Omega = Delta × spot_price / option_price)",
        "type": "float",
        "aliases": ["lev"],
        "example": "leverage>5",
    },
    "lev": {"description": "Alias for 'leverage'", "type": "float", "alias_of": "leverage", "example": "lev>5"},
    "efficiency": {
        "description": "Efficiency percentile (leverage/CAGR, 0-100 scale)",
        "type": "float",
        "aliases": ["eff"],
        "example": "efficiency>80",
    },
    "eff": {"description": "Alias for 'efficiency'", "type": "float", "alias_of": "efficiency", "example": "eff>80"},
}


@dataclass
class FilterNode:
    """Represents a single filter condition"""

    key: str
    operator: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {"key": self.key, "op": self.operator, "value": self.value}


@dataclass
class LogicalNode:
    """Represents a logical operation (AND/OR)"""

    operator: str  # "AND" or "OR"
    children: List[Union["FilterNode", "LogicalNode"]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {"op": self.operator, "children": [child.to_dict() for child in self.children]}


class FilterParseError(Exception):
    """Exception raised for filter parsing errors"""

    pass


def parse_dte_value(value_str: str) -> int:
    """Parse DTE-style time expressions like '1y', '1.5y', '6m', '2w', '30d' into days.

    Supported units:
    - y: years (365 days)
    - m: months (30 days)
    - w: weeks (7 days)
    - d: days

    Args:
        value_str: Time string like "1y", "1.5y", "6m", "2w", "30d"

    Returns:
        Total time in days (integer, rounded)

    Raises:
        FilterParseError: If the time format is invalid
    """
    value_str = value_str.lower().strip()

    # Pattern to match DTE-style expressions: number (with optional decimal) followed by y/m/w/d
    match = re.match(r"^(\d+(?:\.\d+)?)([ymwd])$", value_str)

    if not match:
        raise FilterParseError(f"Invalid DTE time format: {value_str}")

    num = float(match.group(1))
    unit = match.group(2)

    if unit == "y":
        return int(num * 365)
    elif unit == "m":
        return int(num * 30)
    elif unit == "w":
        return int(num * 7)
    elif unit == "d":
        return int(num)
    else:
        raise FilterParseError(f"Unknown unit: {unit}")


def parse_time_value(value_str: str) -> float:
    """Parse time values like '2d15h' into hours.

    Supported units:
    - d: days (24 hours)
    - h: hours
    - m: minutes
    - s: seconds

    Args:
        value_str: Time string like "2d15h", "30m", "1d"

    Returns:
        Total time in hours

    Raises:
        FilterParseError: If the time format is invalid
    """
    value_str = value_str.lower().strip()
    total_hours = 0.0

    # Pattern to match time components like 2d, 15h, 30m, etc.
    # Matches integers or decimals: 2d, 2.5d, 15h, 1.25h, etc.
    # Pattern breakdown: \d+ = one or more digits, (?:\.\d+)? = optional decimal part
    # Note: Requires at least one digit before decimal (0.5d is valid, .5d is not)
    pattern = r"(\d+(?:\.\d+)?)([dhms])"
    matches = re.findall(pattern, value_str)

    if not matches:
        raise FilterParseError(f"Invalid time format: {value_str}")

    for amount, unit in matches:
        amount = float(amount)
        if unit == "d":
            total_hours += amount * 24
        elif unit == "h":
            total_hours += amount
        elif unit == "m":
            total_hours += amount / 60
        elif unit == "s":
            total_hours += amount / 3600

    return total_hours


def parse_value(value_str: str) -> Any:
    """Parse a value string to appropriate type.

    Attempts to parse as:
    1. DTE-style time value (1y, 6m, 2w, 30d) - returns days as integer
    2. Duration time value (2d15h, 30m, etc.) - returns hours as float
    3. Integer
    4. Float
    5. String (fallback)

    Args:
        value_str: String representation of value

    Returns:
        Parsed value in appropriate type
    """
    value_str = value_str.strip()

    # Check for DTE-style time values (e.g., "1y", "1.5y", "6m", "2w")
    # These are simple expressions: number (with optional decimal) + single unit, returning days
    # Note: 'd' is excluded here to preserve backward compatibility with duration parsing (1d = 24h)
    # For day-based filtering, users can use plain integers (e.g., 'dte>30')
    if re.match(r"^\d+(?:\.\d+)?[ymw]$", value_str.lower()):
        try:
            return parse_dte_value(value_str)
        except FilterParseError:
            pass  # Fall through to other parsers

    # Check for duration time values (e.g., "2d15h", "30m")
    # These can be compound expressions, returning hours
    if re.search(r"\d+[dhms]", value_str.lower()):
        try:
            return parse_time_value(value_str)
        except FilterParseError:
            pass  # Fall through to other parsers

    # Try integer
    try:
        return int(value_str)
    except ValueError:
        pass

    # Try float
    try:
        return float(value_str)
    except ValueError:
        pass

    # Return as string
    return value_str


def tokenize_filter(filter_str: str) -> List[str]:
    """Tokenize a filter string into components.

    Splits on logical operators while preserving parentheses and filter expressions.

    Args:
        filter_str: Filter expression string

    Returns:
        List of tokens
    """
    # Remove extra whitespace
    filter_str = " ".join(filter_str.split())

    tokens = []
    current_token = ""
    paren_depth = 0

    for char in filter_str:
        if char == "(":
            if paren_depth == 0 and current_token.strip():
                tokens.append(current_token.strip())
                current_token = ""
            current_token += char
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
            current_token += char
            if paren_depth == 0:
                tokens.append(current_token.strip())
                current_token = ""
        elif char in [",", "+"] and paren_depth == 0:
            if current_token.strip():
                tokens.append(current_token.strip())
            tokens.append(char)
            current_token = ""
        else:
            current_token += char

    if current_token.strip():
        tokens.append(current_token.strip())

    if paren_depth != 0:
        raise FilterParseError("Mismatched parentheses in filter expression")

    return tokens


def parse_single_filter(filter_str: str) -> FilterNode:
    """Parse a single filter expression into a FilterNode.

    Args:
        filter_str: Single filter like "dte>300" or "strike<=100"

    Returns:
        FilterNode representing the parsed filter

    Raises:
        FilterParseError: If filter format is invalid
    """
    # Match operators: >=, <=, !=, =, >, <
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|!=|=|>|<)\s*(.+)$", filter_str.strip())

    if not match:
        raise FilterParseError(f"Invalid filter format: '{filter_str}'. Expected format: key operator value")

    key = match.group(1)
    operator = match.group(2)
    value_str = match.group(3)

    # Normalize = to ==
    if operator == "=":
        operator = "=="

    value = parse_value(value_str)

    return FilterNode(key=key, operator=operator, value=value)


def parse_filter_expression(filter_str: str) -> Union[FilterNode, LogicalNode]:
    """Parse a complete filter expression into an AST.

    Args:
        filter_str: Complete filter expression

    Returns:
        Root node of the filter AST (FilterNode or LogicalNode)

    Raises:
        FilterParseError: If parsing fails
    """
    if not filter_str or not filter_str.strip():
        raise FilterParseError("Empty filter expression")

    filter_str = filter_str.strip()

    # Handle parentheses
    if filter_str.startswith("(") and filter_str.endswith(")"):
        # Check if these are the outermost matching parentheses
        inner = filter_str[1:-1]
        paren_depth = 0
        for char in inner:
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
                if paren_depth < 0:
                    break
        if paren_depth == 0:
            # These are wrapping parens, remove them
            filter_str = inner.strip()

    tokens = tokenize_filter(filter_str)

    if not tokens:
        raise FilterParseError("No tokens found in filter expression")

    # Single token - either a simple filter or parenthesized expression
    if len(tokens) == 1:
        token = tokens[0]
        if token.startswith("(") and token.endswith(")"):
            return parse_filter_expression(token[1:-1])
        return parse_single_filter(token)

    # Process tokens to build AST
    # Strategy: First process AND (,) at top level, then OR (+)
    # This gives AND higher precedence than OR

    # Check for AND operators (comma) at top level
    and_parts = []
    current_part = []

    for token in tokens:
        if token == ",":
            if current_part:
                and_parts.append(current_part)
                current_part = []
        else:
            current_part.append(token)

    if current_part:
        and_parts.append(current_part)

    # If we have multiple AND parts, create AND node
    if len(and_parts) > 1:
        children = []
        for part in and_parts:
            if len(part) == 1 and part[0] not in [",", "+"]:
                # Single token part
                token = part[0]
                if token.startswith("(") and token.endswith(")"):
                    children.append(parse_filter_expression(token[1:-1]))
                else:
                    children.append(parse_single_filter(token))
            else:
                # Multiple tokens - process as OR expression
                children.append(parse_or_expression(part))
        return LogicalNode(operator="AND", children=children)

    # No AND operators, process as OR expression
    return parse_or_expression(tokens)


def parse_or_expression(tokens: List[str]) -> Union[FilterNode, LogicalNode]:
    """Parse OR expression from tokens.

    Args:
        tokens: List of tokens (no commas, may have + operators)

    Returns:
        FilterNode or LogicalNode representing OR expression
    """
    or_parts = []
    current_part = []

    for token in tokens:
        if token == "+":
            if current_part:
                or_parts.append(current_part)
                current_part = []
        elif token == ",":
            # Should not happen at this level
            raise FilterParseError("Unexpected comma in OR expression")
        else:
            current_part.append(token)

    if current_part:
        or_parts.append(current_part)

    # If we have multiple OR parts, create OR node
    if len(or_parts) > 1:
        children = []
        for part in or_parts:
            if len(part) == 1:
                token = part[0]
                if token.startswith("(") and token.endswith(")"):
                    children.append(parse_filter_expression(token[1:-1]))
                else:
                    children.append(parse_single_filter(token))
            else:
                raise FilterParseError(f"Unexpected multiple tokens in OR part: {part}")
        return LogicalNode(operator="OR", children=children)

    # Single part, parse it
    if len(or_parts) == 1 and len(or_parts[0]) == 1:
        token = or_parts[0][0]
        if token.startswith("(") and token.endswith(")"):
            return parse_filter_expression(token[1:-1])
        return parse_single_filter(token)

    raise FilterParseError(f"Failed to parse OR expression from tokens: {tokens}")


def parse_filter(filter_str: str) -> Dict[str, Any]:
    """Parse a filter string and return AST as dictionary.

    This is the main entry point for parsing filters.

    Args:
        filter_str: Filter expression string

    Returns:
        Dictionary representation of the filter AST

    Raises:
        FilterParseError: If parsing fails
    """
    try:
        ast = parse_filter_expression(filter_str)
        return ast.to_dict()
    except FilterParseError:
        raise
    except Exception as e:
        raise FilterParseError(f"Failed to parse filter: {e}") from e


def filter_to_string(filter_dict: Dict[str, Any]) -> str:
    """Convert a filter AST dictionary back to string representation.

    Args:
        filter_dict: Filter AST in dictionary format

    Returns:
        String representation of the filter
    """
    if "key" in filter_dict:
        # FilterNode
        return f"{filter_dict['key']}{filter_dict['op']}{filter_dict['value']}"
    elif "op" in filter_dict and "children" in filter_dict:
        # LogicalNode
        op = filter_dict["op"]
        children_strs = [filter_to_string(child) for child in filter_dict["children"]]
        separator = ", " if op == "AND" else " + "
        return f"({separator.join(children_strs)})"
    else:
        raise ValueError(f"Invalid filter dictionary: {filter_dict}")


def get_filter_help() -> str:
    """Generate formatted help text for available filter fields.

    Returns:
        Formatted help text describing all filter fields, operators, and syntax
    """
    help_lines = []

    # Header
    help_lines.append("Filter Expression Reference")
    help_lines.append("=" * 50)
    help_lines.append("")

    # Available Fields
    help_lines.append("Available Filter Fields:")
    help_lines.append("-" * 50)

    # Group main fields (exclude aliases)
    main_fields = {k: v for k, v in FILTER_FIELDS.items() if "alias_of" not in v}

    for field_name in sorted(main_fields.keys()):
        field_info = main_fields[field_name]
        help_lines.append(f"\n  {field_name}")
        help_lines.append(f"    {field_info['description']}")
        help_lines.append(f"    Type: {field_info['type']}")

        # Show aliases if any
        if "aliases" in field_info:
            aliases_str = ", ".join(field_info["aliases"])
            help_lines.append(f"    Aliases: {aliases_str}")

        help_lines.append(f"    Example: {field_info['example']}")

    # Operators
    help_lines.append("\n")
    help_lines.append("Comparison Operators:")
    help_lines.append("-" * 50)
    help_lines.append("  >   Greater than")
    help_lines.append("  <   Less than")
    help_lines.append("  >=  Greater than or equal")
    help_lines.append("  <=  Less than or equal")
    help_lines.append("  =   Equal (also ==)")
    help_lines.append("  !=  Not equal")

    # Logical Operators
    help_lines.append("\n")
    help_lines.append("Logical Operators:")
    help_lines.append("-" * 50)
    help_lines.append("  ,   AND - all conditions must be true")
    help_lines.append("  +   OR  - at least one condition must be true")
    help_lines.append("  ()  Parentheses for grouping")

    # Time Value Formats
    help_lines.append("\n")
    help_lines.append("Time Value Formats:")
    help_lines.append("-" * 50)
    help_lines.append("  DTE-style (returns days): 1y, 6m, 2w, 30d")
    help_lines.append("  Duration (returns hours): 2d15h, 30m, 1h")
    help_lines.append("  Plain integers: 5, 150, 300")

    # Examples
    help_lines.append("\n")
    help_lines.append("Example Filters:")
    help_lines.append("-" * 50)
    help_lines.append("  dte>150")
    help_lines.append("    Options with more than 150 days to expiry")
    help_lines.append("")
    help_lines.append("  dte>150, lt_days<7")
    help_lines.append("    Options with DTE > 150 AND traded in last 7 days")
    help_lines.append("")
    help_lines.append("  (dte>300 + dte<30), volume>100")
    help_lines.append("    Options with (DTE > 300 OR DTE < 30) AND volume > 100")
    help_lines.append("")
    help_lines.append("  return>0.20, sp>5, sp<15")
    help_lines.append("    Options with return > 20%, strike 5-15% above spot")

    # Named filter presets
    help_lines.append("\n")
    help_lines.append("Named Filter Presets:")
    help_lines.append("-" * 50)
    help_lines.append('  Save:    fplot --save-filter NAME --filter "EXPRESSION"')
    help_lines.append("  Use:     fplot AAPL --put --filter NAME")
    help_lines.append("  List:    fplot --list-filters")
    help_lines.append("  Delete:  fplot --delete-filter NAME")
    help_lines.append("  Default: fplot --default-filter NAME  (applied when no --filter given)")
    help_lines.append("  Clear:   fplot --default-filter none")

    return "\n".join(help_lines)
