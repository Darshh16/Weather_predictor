from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MarketSnapshot(BaseModel):
    city: str
    contract_id: Optional[str] = None
    question: Optional[str] = None
    yes_price: float = 0.5
    no_price: float = 0.5
    volume: float = 0.0
    liquidity: float = 0.0
    resolution_date: Optional[str] = None
    raw_json: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def implied_probability(self) -> float:
        return self.yes_price
