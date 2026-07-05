import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_resolution_pnl_yes_win():
    size = 100
    entry_price = 0.4
    pnl = size * (1 - entry_price) / entry_price
    assert abs(pnl - 150.0) < 0.01

def test_resolution_pnl_yes_loss():
    size = 100
    entry_price = 0.4
    pnl = -size
    assert pnl == -100

def test_resolution_pnl_no_win():
    size = 100
    entry_price = 0.6
    pnl = size * (1 - entry_price) / entry_price
    assert abs(pnl - 66.66) < 0.01

def test_resolution_pnl_no_loss():
    size = 100
    entry_price = 0.6
    pnl = -size
    assert pnl == -100

def test_m2m_equity_calculation():
    balance = 1000
    
    t1_size = 100
    t1_entry = 0.5
    t1_curr = 0.8
    v1 = (t1_size / t1_entry) * t1_curr
    
    t2_size = 50
    t2_entry = 0.4
    t2_curr = 0.2
    v2 = (t2_size / t2_entry) * t2_curr
    
    equity = balance + v1 + v2
    assert abs(equity - 1185.0) < 0.01

def test_win_rate_calculation():
    wins = 3
    losses = 2
    total_trades = wins + losses
    win_rate = round(wins / max(total_trades, 1) * 100, 1)
    assert win_rate == 60.0

if __name__ == "__main__":
    test_resolution_pnl_yes_win()
    test_resolution_pnl_yes_loss()
    test_resolution_pnl_no_win()
    test_resolution_pnl_no_loss()
    test_m2m_equity_calculation()
    test_win_rate_calculation()
    print("All resolution tests passed!")
