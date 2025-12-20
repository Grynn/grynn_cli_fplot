#!/bin/bash
# Example usage of fplot filter features

echo "=== fplot Filter Examples ==="
echo ""
echo "These examples demonstrate the new filter capabilities."
echo "Note: Requires internet connection to fetch live options data."
echo ""

# Basic usage
echo "1. Basic call options listing (default: 6 months max)"
echo "   Command: fplot AAPL --call"
echo ""

# Long-dated options
echo "2. Long-dated call options (300+ days to expiry)"
echo "   Command: fplot AAPL --call --min-dte 300 --all"
echo ""

# Simple filter
echo "3. Filter options with more than 300 days to expiry"
echo "   Command: fplot AAPL --call --filter \"dte>300\" --all"
echo ""

# Range filter (AND)
echo "4. Filter options between 10-50 days to expiry (AND operation)"
echo "   Command: fplot AAPL --call --filter \"dte>10, dte<50\""
echo ""

# OR filter
echo "5. Filter short-term OR long-dated options (OR operation)"
echo "   Command: fplot AAPL --call --filter \"dte<30 + dte>300\" --all"
echo ""

# Strike price filter
echo "6. Filter options by strike price range"
echo "   Command: fplot AAPL --call --filter \"strike>150, strike<200\""
echo ""

# Complex nested filter
echo "7. Complex nested filter: (short-term OR long-dated) AND strike > 150"
echo "   Command: fplot AAPL --call --filter \"(dte<30 + dte>300), strike>150\" --all"
echo ""

# Multiple conditions
echo "8. Multiple conditions: specific date range and strike range"
echo "   Command: fplot AAPL --call --filter \"dte>10, dte<50, strike>150, strike<200\""
echo ""

# Volume filter
echo "9. High volume options (volume >= 100)"
echo "   Command: fplot AAPL --call --filter \"volume>=100\""
echo ""

# Combined with max
echo "10. Using --max with --filter (3 months max, strike > 150)"
echo "    Command: fplot AAPL --call --max 3m --filter \"strike>150\""
echo ""

# Error example
echo "11. Invalid filter (demonstrates error handling)"
echo "    Command: fplot AAPL --call --filter \"invalid filter\""
echo "    Expected: Clear error message with syntax help"
echo ""

echo "=== Filter Syntax Reference ==="
echo ""
echo "Logical Operators:"
echo "  , (comma)  = AND  (all conditions must be true)"
echo "  + (plus)   = OR   (at least one condition must be true)"
echo "  ()         = Grouping for precedence"
echo ""
echo "Comparison Operators:"
echo "  >   = Greater than"
echo "  <   = Less than"
echo "  >=  = Greater than or equal"
echo "  <=  = Less than or equal"
echo "  =   = Equal"
echo "  !=  = Not equal"
echo ""
echo "Available Fields:"
echo "  dte         = Days to expiry"
echo "  volume      = Option volume"
echo "  price       = Last price"
echo "  return      = Return metric (CAGR for calls, annualized return for puts)"
echo "  ret         = Alias for return"
echo "  ar          = Alias for annualized return"
echo "  strike_pct  = Strike % above/below spot (positive = above, negative = below)"
echo "  sp          = Alias for strike_pct"
echo "  lt_days     = Days since last trade"
echo ""
echo "Note: 'strike' (absolute price) and 'spot' are not available as filter fields."
echo "      Use 'strike_pct' or 'sp' for relative strike filtering."
echo ""
echo "Time Values (for custom fields):"
echo "  d = days,  h = hours,  m = minutes,  s = seconds"
echo "  Example: 2d15h = 63 hours"
echo ""
echo "=== To run these examples, uncomment the commands below ==="
echo ""

# Uncomment to run actual examples (requires internet)
# fplot AAPL --call
# fplot AAPL --call --min-dte 300 --all
# fplot AAPL --call --filter "dte>300" --all
# fplot AAPL --call --filter "dte>10, dte<50"
# fplot AAPL --call --filter "dte<30 + dte>300" --all
# fplot AAPL --call --filter "strike>150, strike<200"
# fplot AAPL --call --filter "(dte<30 + dte>300), strike>150" --all
# fplot AAPL --call --filter "invalid filter"
