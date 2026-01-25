# Filter Design Documentation (Step 1)

## Overview

This document describes the design and implementation of the enhanced filter support for options filtering in fplot. This is Step 1 (Design Phase) of the filter enhancement feature.

## Problem Statement

The current `--call` option does not support:
1. Long-dated calls (e.g., options with 300+ days to expiry)
2. Flexible filter specification with multiple conditions
3. Logical operators (AND/OR) for complex filtering

## Solution Design

### 1. CLI Options

Added two new CLI options:

#### `--min-dte <days>`
- Minimum days to expiry filter
- Type: Integer
- Example: `fplot AAPL --call --min-dte 300 --all`
- Use case: Finding long-dated options

#### `--filter <expression>`
- Complex filter expressions with logical operators
- Type: String
- Example: `fplot AAPL --call --filter "dte>300, strike<200"`
- Use case: Advanced filtering with multiple conditions

### 2. Filter Syntax

#### Operators

**Logical Operators:**
- `,` (comma): AND operation - all conditions must be true
- `+` (plus): OR operation - at least one condition must be true
- `()` (parentheses): Grouping for precedence

**Comparison Operators:**
- `>`: Greater than
- `<`: Less than
- `>=`: Greater than or equal
- `<=`: Less than or equal
- `=`: Equal (normalized to `==` internally)
- `!=`: Not equal

#### Filter Fields

The following fields are available for filtering:
- `dte`: Days to expiry (integer)
- `volume`: Option volume (integer)
- `price`: Last price (float)
- `return`, `ret`, `ar`: Return metric - CAGR for calls, annualized return for puts (float)
  - All three aliases reference the same value
- `strike_pct`, `sp`: Strike percentage above/below current spot price (float)
  - Positive values mean strike is above spot (out of the money for calls)
  - Negative values mean strike is below spot (in the money for calls)
  - Example: `sp>5` filters for strikes >5% above spot
- `lt_days`: Days since last trade (integer)
  - Number of days between now and the last trade date
  - Useful for filtering out stale/illiquid options

**Note:** `strike` (absolute strike price) and `spot` (current spot price) are not available as filter fields. Use `strike_pct`/`sp` for strike-based filtering relative to current price.

#### Time Values

Time expressions are supported for convenience:
- Format: `<number><unit>` where unit is `d`, `h`, `m`, or `s`
- Examples: `2d`, `15h`, `30m`, `2d15h`
- Parsed to hours internally
- Example: `"lt_days<=2d15h"` → 63 hours

### 3. Filter AST (Abstract Syntax Tree)

Filters are parsed into a structured AST format for downstream processing.

#### FilterNode (Simple Condition)
```python
{
    "key": str,      # Field name (e.g., "dte", "strike")
    "op": str,       # Operator (e.g., ">", "<=")
    "value": Any     # Value to compare (int, float, str)
}
```

Example:
```python
{"key": "dte", "op": ">", "value": 300}
```

#### LogicalNode (AND/OR Operations)
```python
{
    "op": str,           # "AND" or "OR"
    "children": [        # List of FilterNode or LogicalNode
        {...},
        {...}
    ]
}
```

Example:
```python
{
    "op": "AND",
    "children": [
        {"key": "dte", "op": ">", "value": 10},
        {"key": "dte", "op": "<", "value": 50}
    ]
}
```

### 4. Parser Implementation

The filter parser is implemented in `grynn_fplot/filter_parser.py` with the following components:

#### Tokenizer
- Splits filter expression into tokens
- Handles parentheses and nested expressions
- Validates matching parentheses

#### Parser
- Converts tokens to AST
- Implements operator precedence (AND has higher precedence than OR)
- Supports nested expressions

#### Value Parser
- Auto-detects value types (int, float, string)
- Parses time expressions (e.g., "2d15h")
- Returns appropriate Python types

### 5. Filter Evaluation

The `evaluate_filter()` function in `grynn_fplot/core.py` evaluates a filter AST against data:

```python
def evaluate_filter(filter_ast: dict, data: dict) -> bool:
    """Evaluate a filter AST against data.

    Args:
        filter_ast: Parsed filter AST
        data: Dictionary with option data

    Returns:
        True if data passes filter, False otherwise
    """
```

Implementation:
- Recursively evaluates AST nodes
- Handles comparison operations for FilterNode
- Handles AND/OR operations for LogicalNode
- Returns False for missing keys or invalid operators

## Usage Examples

### Basic Filtering

```bash
# Single condition
fplot AAPL --call --filter "dte>300"

# Time-based filtering
fplot AAPL --call --filter "dte<=2d15h"  # Note: dte is in days, this example is illustrative
```

### AND Operations

```bash
# Multiple conditions (all must be true)
fplot AAPL --call --filter "dte>10, dte<50"
fplot AAPL --call --filter "strike>100, strike<200, volume>=100"
```

### OR Operations

```bash
# At least one condition must be true
fplot AAPL --call --filter "dte<30 + dte>300"
fplot AAPL --call --filter "strike<100 + strike>200"
```

### Complex Nested Filters

```bash
# (dte>300 OR dte<30) AND strike>150
fplot AAPL --call --filter "(dte>300 + dte<30), strike>150"

# (dte>10 AND dte<50) OR (strike>150 AND strike<200)
fplot AAPL --call --filter "(dte>10, dte<50) + (strike>150, strike<200)"
```

### Combined with Other Options

```bash
# Long-dated calls with min-dte
fplot AAPL --call --min-dte 300 --all

# Filter with max expiry
fplot AAPL --call --max 3m --filter "strike>100, volume>=50"

# Complex filter on long-dated options
fplot AAPL --call --all --filter "dte>300, strike>150, strike<200"
```

## Error Handling

The parser provides clear error messages for invalid syntax:

```bash
# Invalid filter
$ fplot AAPL --call --filter "invalid filter"
Error: Invalid filter expression: Invalid filter format: 'invalid filter'. Expected format: key operator value
Filter syntax: Use comma (,) for AND, plus (+) for OR
Examples: 'dte>300', 'dte>10, dte<15', 'dte>300 + strike<100'
```

Common errors:
- Missing operator: `"dte 300"` → Error
- Invalid operator: `"dte ~ 300"` → Error
- Mismatched parentheses: `"(dte>10"` → Error
- Empty expression: `""` → Error

## Implementation Details

### Module Structure

```
grynn_fplot/
├── filter_parser.py      # Filter parsing and AST generation
├── core.py               # Filter evaluation and options display
└── cli.py                # CLI interface

tests/
├── test_filter_parser.py      # Parser tests (40 tests)
├── test_filter_evaluation.py  # Evaluation tests (12 tests)
└── test_cli_options.py        # CLI tests (12 tests, including 4 new)
```

### Key Functions

#### `parse_filter(filter_str: str) -> Dict[str, Any]`
Main entry point for parsing filter expressions. Returns AST as dictionary.

#### `evaluate_filter(filter_ast: dict, data: dict) -> bool`
Evaluates a filter AST against option data. Returns True if data passes filter.

#### `format_options_for_display(..., filter_ast: dict = None)`
Updated to accept filter AST and apply filtering to options before display.

## Future Enhancements (Step 2+)

Potential future improvements:
1. SQL query generation from AST
2. More filter fields (Greeks: delta, gamma, theta, vega)
3. Computed fields (e.g., `moneyness`, `itm/otm`)
4. Range expressions (e.g., `dte:10-50` as shorthand for `dte>10, dte<50`)
5. Pattern matching for strings (e.g., `symbol~AAPL*`)
6. Filter presets/saved filters
7. Filter suggestions based on common patterns

## Testing

Total tests: 103 (56 new tests added)

### Test Coverage

1. **Filter Parser Tests** (40 tests in `test_filter_parser.py`)
   - Time value parsing (6 tests)
   - Value parsing (4 tests)
   - Tokenization (6 tests)
   - Single filter parsing (8 tests)
   - Complex filter parsing (10 tests)
   - Filter to string conversion (4 tests)
   - FilterNode dataclass (2 tests)

2. **Filter Evaluation Tests** (12 tests in `test_filter_evaluation.py`)
   - Comparison operators (6 tests)
   - Logical operators (2 tests)
   - Nested filters (1 test)
   - Edge cases (3 tests)

3. **CLI Tests** (4 new tests in `test_cli_options.py`)
   - `--min-dte` flag
   - `--filter` flag (simple)
   - `--filter` flag (complex)
   - Invalid filter error handling

All tests passing: ✅

## Performance Considerations

1. **Parsing**: Filter expressions are parsed once at CLI invocation
2. **Evaluation**: O(n) complexity where n is number of options
3. **Caching**: Options data is cached for 1 hour (unchanged)
4. **Minimal overhead**: Filter evaluation adds negligible overhead compared to API calls

## Backwards Compatibility

All existing functionality is preserved:
- Existing CLI options work unchanged
- New options are optional and don't affect existing behavior
- No breaking changes to `format_options_for_display()` (new parameters are optional)

## Conclusion

This design provides a flexible, extensible framework for options filtering that:
- ✅ Supports long-dated options via `--min-dte`
- ✅ Provides complex filtering via `--filter` with AND/OR logic
- ✅ Uses AST representation for future extensibility
- ✅ Has comprehensive test coverage (56 new tests)
- ✅ Maintains backwards compatibility
- ✅ Provides clear error messages
- ✅ Is ready for Step 2 implementation (SQL generation, more fields, etc.)
