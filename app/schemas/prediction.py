from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PredictionRequest(BaseModel):
    city: str


class PredictionResult(BaseModel):
    city: str
    model_probability: float = 0.5
    market_probability: float = 0.5
    edge: float = 0.0
    recommendation: str = "HOLD"
    reasoning: str = ""
    confidence: float = 0.0
    weather_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_edge(self) -> bool:
        return abs(self.edge) > 0.02

    @property
    def direction(self) -> str:
        if self.edge > 0:
            return "YES"
        elif self.edge < 0:
            return "NO"
        return "NONE"
