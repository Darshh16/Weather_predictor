import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.risk_agent import RiskAgent
from app.schemas.prediction import PredictionResult


def test_kelly_basic_edge():
    agent = RiskAgent()
    pred = PredictionResult(city="test", model_probability=0.6, market_probability=0.5, edge=0.1, recommendation="BUY YES")
    sizing = agent.compute_kelly(pred, 10000)
    assert sizing.fraction > 0
    assert sizing.position_size > 0
    assert sizing.position_size <= 10000 * agent.max_kelly


def test_kelly_no_edge():
    agent = RiskAgent()
    pred = PredictionResult(city="test", model_probability=0.5, market_probability=0.5, edge=0.0, recommendation="HOLD")
    sizing = agent.compute_kelly(pred, 10000)
    assert sizing.fraction == 0
    assert sizing.position_size == 0


def test_kelly_negative_edge():
    agent = RiskAgent()
    pred = PredictionResult(city="test", model_probability=0.3, market_probability=0.5, edge=-0.2, recommendation="BUY NO")
    sizing = agent.compute_kelly(pred, 10000)
    assert sizing.fraction >= 0
    assert sizing.position_size >= 0


def test_kelly_high_edge_capped():
    agent = RiskAgent()
    pred = PredictionResult(city="test", model_probability=0.95, market_probability=0.2, edge=0.75, recommendation="BUY YES")
    sizing = agent.compute_kelly(pred, 10000)
    assert sizing.capped
    assert sizing.fraction <= agent.max_kelly


def test_kelly_symmetry():
    agent = RiskAgent()
    pred_yes = PredictionResult(city="test", model_probability=0.7, market_probability=0.5, edge=0.2, recommendation="BUY YES")
    pred_no = PredictionResult(city="test", model_probability=0.3, market_probability=0.5, edge=-0.2, recommendation="BUY NO")
    size_yes = agent.compute_kelly(pred_yes, 10000)
    size_no = agent.compute_kelly(pred_no, 10000)
    assert abs(size_yes.raw_kelly - size_no.raw_kelly) < 0.01


def test_exposure_cap():
    agent = RiskAgent()
    capped = agent.check_portfolio_exposure(4000, 2000, 10000)
    assert capped <= 10000 * agent.max_exposure_portfolio - 4000


if __name__ == "__main__":
    test_kelly_basic_edge()
    test_kelly_no_edge()
    test_kelly_negative_edge()
    test_kelly_high_edge_capped()
    test_kelly_symmetry()
    test_exposure_cap()
    print("All Kelly tests passed!")
