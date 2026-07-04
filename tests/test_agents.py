import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.weather import WeatherData, WeatherReport, SourceValidation
from app.schemas.market import MarketSnapshot
from app.schemas.prediction import PredictionResult
from app.schemas.trading import Trade, KellySizing, PortfolioState
from app.prompts.prediction_prompt import build_prediction_prompt


def test_weather_data_creation():
    w = WeatherData(city="new_york", source="openweather", temperature=25.0, humidity=60)
    assert w.city == "new_york"
    assert w.temperature == 25.0


def test_market_snapshot_implied_prob():
    m = MarketSnapshot(city="london", yes_price=0.65, no_price=0.35)
    assert m.implied_probability == 0.65


def test_prediction_has_edge():
    p = PredictionResult(city="tokyo", model_probability=0.7, market_probability=0.5, edge=0.2, recommendation="BUY YES")
    assert p.has_edge
    assert p.direction == "YES"


def test_prediction_no_edge():
    p = PredictionResult(city="tokyo", model_probability=0.51, market_probability=0.5, edge=0.01)
    assert not p.has_edge
    p_zero = PredictionResult(city="tokyo", model_probability=0.5, market_probability=0.5, edge=0.0)
    assert p_zero.direction == "NONE"


def test_build_prompt():
    weather = WeatherReport(
        city="new_york",
        sources=[WeatherData(city="new_york", source="test", temperature=22)],
        validation=SourceValidation(sources_count=1, confidence_score=0.5),
        consensus_temperature=22,
    )
    market = MarketSnapshot(city="new_york", yes_price=0.55, no_price=0.45, volume=10000)
    messages = build_prediction_prompt(weather, market)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "new_york" in messages[1]["content"]
    assert "0.55" in messages[1]["content"]


def test_trade_creation():
    t = Trade(city="london", direction="YES", size=500, entry_price=0.45, trade_type="open")
    assert t.status == "open"
    assert t.pnl == 0.0


def test_portfolio_state():
    p = PortfolioState(balance=9500, equity=10200, wins=3, losses=1, total_trades=4)
    assert p.win_rate == 0.0  # computed separately in agent


def test_kelly_sizing():
    k = KellySizing(fraction=0.1, position_size=1000, risk_score=0.3, capped=False, raw_kelly=0.2)
    assert k.position_size == 1000


if __name__ == "__main__":
    test_weather_data_creation()
    test_market_snapshot_implied_prob()
    test_prediction_has_edge()
    test_prediction_no_edge()
    test_build_prompt()
    test_trade_creation()
    test_portfolio_state()
    test_kelly_sizing()
    print("All agent/schema tests passed!")
