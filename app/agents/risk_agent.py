from app.schemas.trading import KellySizing
from app.schemas.prediction import PredictionResult
from app.core.config import get_settings
from loguru import logger


class RiskAgent:
    def __init__(self):
        s = get_settings()
        self.max_kelly = s.max_kelly_fraction
        self.max_exposure_market = s.max_exposure_per_market
        self.max_exposure_portfolio = s.max_portfolio_exposure

    def compute_kelly(self, prediction: PredictionResult, balance: float) -> KellySizing:
        p = prediction.model_probability
        market_price = prediction.market_probability
        if prediction.recommendation == "BUY NO":
            p = 1 - p
            market_price = 1 - market_price
        q = 1 - p
        b = (1 / market_price) - 1 if market_price > 0 else 0
        if b <= 0:
            return KellySizing(fraction=0, position_size=0, risk_score=1.0, capped=False, raw_kelly=0)
        raw_kelly = (b * p - q) / b
        raw_kelly = max(0, raw_kelly)
        half_kelly = raw_kelly * 0.5
        capped = half_kelly > self.max_kelly
        fraction = min(half_kelly, self.max_kelly)
        max_market_size = balance * self.max_exposure_market
        position_size = min(balance * fraction, max_market_size)
        risk_score = self._compute_risk_score(prediction, fraction)
        logger.info(
            f"Kelly for {prediction.city}: raw={raw_kelly:.4f}, half={half_kelly:.4f}, "
            f"capped={capped}, size=${position_size:.2f}, risk={risk_score:.2f}"
        )
        return KellySizing(
            fraction=round(fraction, 4),
            position_size=round(position_size, 2),
            risk_score=round(risk_score, 2),
            capped=capped,
            raw_kelly=round(raw_kelly, 4),
        )

    def _compute_risk_score(self, prediction: PredictionResult, fraction: float) -> float:
        edge_factor = min(abs(prediction.edge) / 0.1, 1.0)
        confidence_factor = prediction.confidence
        size_factor = 1.0 - min(fraction / self.max_kelly, 1.0)
        return round(1.0 - (edge_factor * 0.4 + confidence_factor * 0.4 + size_factor * 0.2), 2)

    def check_portfolio_exposure(self, current_exposure: float, new_size: float, balance: float) -> float:
        max_total = balance * self.max_exposure_portfolio
        available = max(0, max_total - current_exposure)
        return min(new_size, available)


risk_agent = RiskAgent()
