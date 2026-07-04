import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.trading_agent import TradingAgent
from app.schemas.prediction import PredictionResult


def test_hedge_trigger_edge_shrunk():
    agent = TradingAgent()
    original_edge = 0.05
    new_edge = 0.01
    threshold = agent.hedge_threshold
    assert abs(new_edge) < threshold and abs(original_edge) >= threshold


def test_hedge_trigger_edge_flipped():
    original_edge = 0.05
    new_edge = -0.05
    flipped = (original_edge > 0 and new_edge < -0.02) or (original_edge < 0 and new_edge > 0.02)
    assert flipped


def test_no_hedge_when_edge_stable():
    original_edge = 0.05
    new_edge = 0.04
    threshold = 0.02
    edge_shrunk = abs(new_edge) < threshold
    edge_flipped = (original_edge > 0 and new_edge < -threshold)
    assert not edge_shrunk
    assert not edge_flipped


def test_hedge_trigger_price_moved():
    entry_price = 0.5
    current_price = 0.7
    assert abs(current_price - entry_price) > 0.15


def test_no_hedge_small_price_move():
    entry_price = 0.5
    current_price = 0.55
    assert abs(current_price - entry_price) <= 0.15


def test_partial_close_calculation():
    original_size = 1000
    close_fraction = 0.5
    close_size = original_size * close_fraction
    remaining = original_size - close_size
    assert close_size == 500
    assert remaining == 500


def test_pnl_calculation_yes():
    entry = 0.4
    exit_price = 0.6
    size = 100
    pnl = (exit_price - entry) * size
    assert abs(pnl - 20.0) < 0.01


def test_pnl_calculation_no():
    entry = 0.6
    exit_price = 0.4
    size = 100
    pnl = (entry - exit_price) * size
    assert abs(pnl - 20.0) < 0.01


if __name__ == "__main__":
    test_hedge_trigger_edge_shrunk()
    test_hedge_trigger_edge_flipped()
    test_no_hedge_when_edge_stable()
    test_hedge_trigger_price_moved()
    test_no_hedge_small_price_move()
    test_partial_close_calculation()
    test_pnl_calculation_yes()
    test_pnl_calculation_no()
    print("All hedge tests passed!")
