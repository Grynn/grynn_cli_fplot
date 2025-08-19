#!/bin/bash

# Example usage script showing how to use fplot with fzf for interactive option selection
# This would be used by end users to filter and select options

echo "Example: Interactive Option Selection with fzf"
echo "=============================================="
echo ""

echo "1. List all AAPL call options:"
echo "   $ fplot AAPL --call"
echo ""

echo "2. Use with fzf for interactive filtering:"
echo "   $ fplot AAPL --call | fzf"
echo ""

echo "3. Select an option and use it in a script:"
echo "   $ selected_option=\$(fplot AAPL --call | fzf)"
echo "   $ echo \"You selected: \$selected_option\""
echo ""

echo "4. Example output format:"
echo "   AAPL 150C 30DTE"
echo "   AAPL 155C 30DTE" 
echo "   AAPL 160C 30DTE"
echo ""

echo "5. Filter by specific criteria:"
echo "   $ fplot AAPL --call | fzf --query='150'"
echo "   $ fplot AAPL --put | fzf --query='DTE'"
echo ""

echo "6. Integration with other tools:"
echo "   $ option=\$(fplot TSLA --call | fzf)"
echo "   $ echo \"\$option\" | awk '{print \$2}' | sed 's/C//' # Extract strike price"
echo ""

# If fzf is available, demonstrate actual usage
if command -v fzf &> /dev/null; then
    echo "fzf is available! You could run:"
    echo "  $ fplot AAPL --call | fzf"
    echo "to interactively select options"
else
    echo "Install fzf for interactive filtering:"
    echo "  $ sudo apt install fzf"
    echo "  or"
    echo "  $ brew install fzf"
fi

echo ""
echo "Happy trading! 📈"