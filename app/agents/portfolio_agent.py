from typing import List
from app.schemas.trading import Trade, PortfolioState
from app.database.connection import fetch_all, fetch_one
from app.core.config import get_settings
from loguru import logger


class PortfolioAgent:
    async def get_state(self) -> PortfolioState:
        portfolio = await fetch_one("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        if not portfolio:
            return PortfolioState(balance=get_settings().initial_bankroll, equity=get_settings().initial_bankroll)
        open_positions = await fetch_all("SELECT * FROM trades WHERE status='open' ORDER BY created_at DESC")
        recent = await fetch_all("SELECT * FROM trades ORDER BY created_at DESC LIMIT 20")
        hedges = await fetch_all(
            "SELECT * FROM trades WHERE trade_type='hedge' ORDER BY created_at DESC LIMIT 10"
        )
        open_exposure = sum(t["size"] for t in open_positions)
        total_trades = portfolio["total_trades"]
        wins = portfolio["wins"]
        return PortfolioState(
            balance=portfolio["balance"],
            equity=portfolio["balance"] + open_exposure,
            total_trades=total_trades,
            open_trades=len(open_positions),
            wins=wins,
            losses=portfolio["losses"],
            total_pnl=portfolio["total_pnl"],
            max_drawdown=portfolio["max_drawdown"],
            win_rate=round(wins / max(total_trades, 1) * 100, 1),
            open_positions=[Trade(**t) for t in open_positions],
            recent_trades=[Trade(**t) for t in recent],
            recent_hedges=[Trade(**t) for t in hedges],
        )

    async def get_open_exposure(self) -> float:
        rows = await fetch_all("SELECT SUM(size) as total FROM trades WHERE status='open'")
        return rows[0]["total"] or 0 if rows else 0

    async def get_city_exposure(self, city: str) -> float:
        rows = await fetch_all(
            "SELECT SUM(size) as total FROM trades WHERE city=? AND status='open'", (city,)
        )
        return rows[0]["total"] or 0 if rows else 0


portfolio_agent = PortfolioAgent()
