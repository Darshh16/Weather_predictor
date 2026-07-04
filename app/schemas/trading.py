from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TradeType(str, Enum):
    OPEN = "open"
    HEDGE = "hedge"
    CLOSE = "close"


class TradeDirection(str, Enum):
    YES = "YES"
    NO = "NO"


class TradeAction(BaseModel):
    city: str
    trade_type: TradeType = TradeType.OPEN
    direction: TradeDirection = TradeDirection.YES
    size: float = 0.0
    entry_price: float = 0.0
    kelly_fraction: float = 0.0
    edge: float = 0.0
    reasoning: str = ""
    prediction_id: Optional[int] = None
    parent_trade_id: Optional[int] = None


class Trade(BaseModel):
    id: Optional[int] = None
    city: str
    trade_type: str = "open"
    direction: str = "YES"
    size: float = 0.0
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    pnl: float = 0.0
    kelly_fraction: float = 0.0
    edge_at_entry: float = 0.0
    edge_at_action: Optional[float] = None
    reasoning: str = ""
    prediction_id: Optional[int] = None
    parent_trade_id: Optional[int] = None
    status: str = "open"
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class HedgeEvent(BaseModel):
    original_trade: Trade
    trigger_reason: str
    pre_edge: float
    post_edge: float
    action_taken: str
    new_trade: Optional[Trade] = None


class PortfolioState(BaseModel):
    balance: float = 10000.0
    equity: float = 10000.0
    total_trades: int = 0
    open_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    open_positions: List[Trade] = Field(default_factory=list)
    recent_trades: List[Trade] = Field(default_factory=list)
    recent_hedges: List[Trade] = Field(default_factory=list)


class KellySizing(BaseModel):
    fraction: float = 0.0
    position_size: float = 0.0
    risk_score: float = 0.0
    capped: bool = False
    raw_kelly: float = 0.0
