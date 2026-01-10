#!/usr/bin/env python3
"""Test for corrected implied leverage calculation with Black-Scholes delta"""

import math
from scipy.stats import norm

def calculate_black_scholes_delta(spot_price: float, strike: float, time_to_expiry: float, 
                                  risk_free_rate: float = 0.05, volatility: float = 0.30,
                                  option_type: str = "call") -> float:
    """Calculate Black-Scholes delta for an option"""
    if spot_price <= 0 or strike <= 0 or time_to_expiry <= 0:
        return 0.0
    
    # Calculate d1 from Black-Scholes formula
    d1 = (math.log(spot_price / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / \
         (volatility * math.sqrt(time_to_expiry))
    
    # Delta for call: N(d1)
    # Delta for put: N(d1) - 1
    if option_type.lower() in ["call", "calls"]:
        return norm.cdf(d1)
    else:  # put
        return norm.cdf(d1) - 1


def calculate_implied_leverage(spot_price: float, option_price: float, strike: float,
                               time_to_expiry: float, option_type: str = "call",
                               risk_free_rate: float = 0.05, volatility: float = 0.30) -> float:
    """Calculate implied leverage (Omega) for an option
    
    Formula: Ω = Δ × (S / O)
    """
    if option_price <= 0 or spot_price <= 0:
        return 0.0

    # Calculate delta using Black-Scholes
    delta = calculate_black_scholes_delta(spot_price, strike, time_to_expiry, 
                                          risk_free_rate, volatility, option_type)
    
    # Omega = Delta × (S / O)
    leverage = abs(delta) * (spot_price / option_price)
    
    return leverage


# Test cases with realistic scenarios
test_cases = [
    # (spot, strike, option_price, dte_days, option_type, description)
    (100, 100, 5.0, 90, "call", "ATM call, 90 DTE"),
    (100, 110, 3.0, 90, "call", "OTM call (+10%), 90 DTE"),
    (100, 90, 12.0, 90, "call", "ITM call (-10%), 90 DTE"),
    (100, 100, 5.0, 30, "call", "ATM call, 30 DTE (shorter)"),
    (100, 100, 5.0, 180, "call", "ATM call, 180 DTE (longer)"),
    (100, 100, 5.0, 90, "put", "ATM put, 90 DTE"),
    (100, 110, 12.0, 90, "put", "ITM put (+10%), 90 DTE"),
    (100, 90, 3.0, 90, "put", "OTM put (-10%), 90 DTE"),
]

print("=" * 90)
print("Testing Corrected Implied Leverage Formula: Ω = Δ × (S / O)")
print("=" * 90)
print()

for spot, strike, price, dte, opt_type, description in test_cases:
    time_to_expiry = dte / 365.0
    
    delta = calculate_black_scholes_delta(spot, strike, time_to_expiry, option_type=opt_type)
    leverage = calculate_implied_leverage(spot, price, strike, time_to_expiry, opt_type)
    
    # Simple leverage (old formula) for comparison
    simple_leverage = spot / price
    
    print(f"📊 {description}")
    print(f"   Spot: ${spot:.2f}, Strike: ${strike:.2f}, Price: ${price:.2f}, DTE: {dte} days")
    print(f"   Delta (Δ): {delta:+.4f}")
    print(f"   S/O ratio: {spot/price:.2f}")
    print(f"   ✓ Implied Leverage (Ω): {leverage:.2f}x  (Δ × S/O = {delta:.4f} × {spot/price:.2f})")
    print(f"   ✗ Simple leverage (old): {simple_leverage:.2f}x  (incorrect - ignores delta)")
    print()

print("=" * 90)
print("Key Insights:")
print("=" * 90)
print("1. Delta adjusts for moneyness:")
print("   - ITM options: Higher delta (~0.7-0.9) → Higher leverage")
print("   - ATM options: Medium delta (~0.5) → Medium leverage")
print("   - OTM options: Lower delta (~0.2-0.4) → Lower leverage")
print()
print("2. Time to expiry affects delta:")
print("   - Longer DTE → Delta closer to intrinsic value")
print("   - Shorter DTE → Delta more sensitive to moneyness")
print()
print("3. Leverage interpretation:")
print("   - 10x leverage: 1% stock move → ~10% option move")
print("   - Higher leverage = more volatile, higher risk/reward")
print()
print("4. Why delta matters:")
print("   - Deep OTM options have low delta → lower actual leverage than S/O suggests")
print("   - ITM options have high delta → leverage closer to S/O ratio")
print("=" * 90)
