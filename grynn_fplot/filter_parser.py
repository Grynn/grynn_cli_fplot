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
    # Matches integers or decimals: 2d, 2.5d, 15h, etc.
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
    1. Time value (if contains time units: d, h, m, s)
    2. Integer
    3. Float
    4. String (fallback)

    Args:
        value_str: String representation of value

    Returns:
        Parsed value in appropriate type
    """
    value_str = value_str.strip()

    # Check for time values (e.g., "2d15h", "30m")
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
