"""Unit tests for implied leverage calculation with Black-Scholes delta"""

from grynn_fplot.core import calculate_black_scholes_delta, calculate_implied_leverage


class TestBlackScholesDelta:
    """Test Black-Scholes delta calculation"""
    
    def test_atm_call_delta(self):
        """ATM call should have delta around 0.5-0.6"""
        delta = calculate_black_scholes_delta(
            spot_price=100, strike=100, time_to_expiry=90/365.0, 
            volatility=0.30, option_type="call"
        )
        assert 0.5 <= delta <= 0.65, f"ATM call delta {delta} outside expected range"
    
    def test_itm_call_delta(self):
        """ITM call should have higher delta (0.7-0.9)"""
        delta = calculate_black_scholes_delta(
            spot_price=100, strike=90, time_to_expiry=90/365.0, 
            volatility=0.30, option_type="call"
        )
        assert 0.7 <= delta <= 0.9, f"ITM call delta {delta} outside expected range"
    
    def test_otm_call_delta(self):
        """OTM call should have lower delta (0.2-0.4)"""
        delta = calculate_black_scholes_delta(
            spot_price=100, strike=110, time_to_expiry=90/365.0, 
            volatility=0.30, option_type="call"
        )
        assert 0.2 <= delta <= 0.5, f"OTM call delta {delta} outside expected range"
    
    def test_atm_put_delta(self):
        """ATM put should have delta around -0.35 to -0.5"""
        delta = calculate_black_scholes_delta(
            spot_price=100, strike=100, time_to_expiry=90/365.0, 
            volatility=0.30, option_type="put"
        )
        assert -0.5 <= delta <= -0.35, f"ATM put delta {delta} outside expected range"
    
    def test_zero_inputs(self):
        """Zero inputs should return 0"""
        assert calculate_black_scholes_delta(0, 100, 0.25, option_type="call") == 0.0
        assert calculate_black_scholes_delta(100, 0, 0.25, option_type="call") == 0.0
        assert calculate_black_scholes_delta(100, 100, 0, option_type="call") == 0.0
    
    def test_call_vs_put_delta(self):
        """Call and put deltas should differ by approximately 1"""
        call_delta = calculate_black_scholes_delta(
            spot_price=100, strike=100, time_to_expiry=90/365.0, option_type="call"
        )
        put_delta = calculate_black_scholes_delta(
            spot_price=100, strike=100, time_to_expiry=90/365.0, option_type="put"
        )
        # Put-call parity: delta_call - delta_put ≈ 1
        assert abs((call_delta - put_delta) - 1.0) < 0.01


class TestImpliedLeverage:
    """Test implied leverage (Omega) calculation"""
    
    def test_leverage_formula(self):
        """Leverage should equal Delta × (S/O)"""
        spot = 100
        strike = 100
        price = 5.0
        dte = 90/365.0
        iv = 0.35  # 35% implied volatility
        
        delta = calculate_black_scholes_delta(spot, strike, dte, volatility=iv, option_type="call")
        leverage = calculate_implied_leverage(spot, price, strike, dte, option_type="call", volatility=iv)
        
        expected_leverage = abs(delta) * (spot / price)
        assert abs(leverage - expected_leverage) < 0.01
    
    def test_leverage_positive(self):
        """Leverage should always be positive"""
        iv = 0.30
        leverage_call = calculate_implied_leverage(100, 5.0, 100, 90/365.0, "call", volatility=iv)
        leverage_put = calculate_implied_leverage(100, 5.0, 100, 90/365.0, "put", volatility=iv)
        
        assert leverage_call > 0
        assert leverage_put > 0
    
    def test_leverage_increases_with_lower_price(self):
        """Lower option price should result in higher leverage (all else equal)"""
        iv = 0.25
        leverage_high_price = calculate_implied_leverage(100, 10.0, 100, 90/365.0, "call", volatility=iv)
        leverage_low_price = calculate_implied_leverage(100, 5.0, 100, 90/365.0, "call", volatility=iv)
        
        assert leverage_low_price > leverage_high_price
    
    def test_otm_vs_itm_leverage(self):
        """OTM options should have different leverage characteristics than ITM"""
        iv = 0.30
        # OTM call: lower delta, but higher S/O ratio
        otm_leverage = calculate_implied_leverage(100, 3.0, 110, 90/365.0, "call", volatility=iv)
        
        # ITM call: higher delta, but lower S/O ratio
        itm_leverage = calculate_implied_leverage(100, 12.0, 90, 90/365.0, "call", volatility=iv)
        
        # Both should be positive
        assert otm_leverage > 0
        assert itm_leverage > 0
    
    def test_zero_price_returns_zero(self):
        """Zero option price should return 0 leverage"""
        leverage = calculate_implied_leverage(100, 0, 100, 90/365.0, "call", volatility=0.30)
        assert leverage == 0.0
    
    def test_zero_spot_returns_zero(self):
        """Zero spot price should return 0 leverage"""
        leverage = calculate_implied_leverage(0, 5.0, 100, 90/365.0, "call", volatility=0.30)
        assert leverage == 0.0
    
    def test_leverage_with_different_volatilities(self):
        """Higher volatility should affect leverage through delta"""
        low_vol_leverage = calculate_implied_leverage(
            100, 5.0, 100, 90/365.0, "call", volatility=0.20
        )
        high_vol_leverage = calculate_implied_leverage(
            100, 5.0, 100, 90/365.0, "call", volatility=0.40
        )
        
        # Both should be positive and reasonably close
        assert low_vol_leverage > 0
        assert high_vol_leverage > 0
        # Volatility affects delta, which affects leverage
        assert abs(low_vol_leverage - high_vol_leverage) < 5.0
    
    def test_realistic_leverage_ranges(self):
        """Leverage should be in realistic ranges for typical options"""
        iv = 0.30  # 30% implied volatility (typical)
        
        # ATM option
        atm_leverage = calculate_implied_leverage(100, 5.0, 100, 90/365.0, "call", volatility=iv)
        assert 5 <= atm_leverage <= 20, f"ATM leverage {atm_leverage} outside realistic range"
        
        # Deep OTM option (cheaper, but low delta)
        otm_leverage = calculate_implied_leverage(100, 2.0, 120, 90/365.0, "call", volatility=iv)
        assert 0 <= otm_leverage <= 30, f"OTM leverage {otm_leverage} outside realistic range"
        
        # ITM option (expensive, high delta)
        itm_leverage = calculate_implied_leverage(100, 15.0, 90, 90/365.0, "call", volatility=iv)
        assert 3 <= itm_leverage <= 15, f"ITM leverage {itm_leverage} outside realistic range"
    
    def test_high_vs_low_implied_volatility(self):
        """Higher implied volatility should affect leverage through delta changes"""
        # Low IV scenario (calm market)
        low_iv = 0.15
        low_iv_leverage = calculate_implied_leverage(
            100, 5.0, 100, 90/365.0, "call", volatility=low_iv
        )
        
        # High IV scenario (volatile market)
        high_iv = 0.60
        high_iv_leverage = calculate_implied_leverage(
            100, 5.0, 100, 90/365.0, "call", volatility=high_iv
        )
        
        # Both should be positive
        assert low_iv_leverage > 0
        assert high_iv_leverage > 0
        
        # High IV typically results in lower delta for ATM options, thus lower leverage
        # (though the relationship is complex and depends on moneyness)
        assert abs(low_iv_leverage - high_iv_leverage) > 0.05  # Should be noticeably different
