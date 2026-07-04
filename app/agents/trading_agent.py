from typing import Optional, List
from app.schemas.trading import Trade, TradeAction, TradeType, TradeDirection, HedgeEvent
from app.schemas.prediction import PredictionResult
from app.schemas.trading import KellySizing
from app.core.config import get_settings
from app.database.connection import execute, fetch_all, fetch_one
from loguru import logger
from datetime import datetime


class TradingAgent:
    def __init__(self):
        self.hedge_threshold = get_settings().hedge_edge_threshold

    async def execute_trade(self, prediction: PredictionResult, sizing: KellySizing,
                            prediction_id: int = None) -> Optional[Trade]:
        if prediction.recommendation == "HOLD" or sizing.position_size <= 0:
            logger.info(f"No trade for {prediction.city}: rec={prediction.recommendation}, size={sizing.position_size}")
            return None
        portfolio = await fetch_one("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        balance = portfolio["balance"] if portfolio else get_settings().initial_bankroll
        if sizing.position_size > balance * 0.5:
            logger.warning(f"Position too large for {prediction.city}, capping")
            sizing.position_size = round(balance * 0.25, 2)
        direction = "YES" if prediction.recommendation == "BUY YES" else "NO"
        entry_price = prediction.market_probability if direction == "YES" else (1 - prediction.market_probability)
        trade = Trade(
            city=prediction.city,
            trade_type="open",
            direction=direction,
            size=sizing.position_size,
            entry_price=entry_price,
            kelly_fraction=sizing.fraction,
            edge_at_entry=prediction.edge,
            reasoning=f"{prediction.recommendation}: edge={prediction.edge:.4f}, kelly={sizing.fraction:.4f}",
            prediction_id=prediction_id,
            status="open",
        )
        cursor = await execute(
            """INSERT INTO trades (city, trade_type, direction, size, entry_price, kelly_fraction,
               edge_at_entry, reasoning, prediction_id, status) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (trade.city, trade.trade_type, trade.direction, trade.size, trade.entry_price,
             trade.kelly_fraction, trade.edge_at_entry, trade.reasoning, trade.prediction_id, trade.status),
        )
        trade.id = cursor.lastrowid
        new_balance = balance - sizing.position_size
        await execute(
            """UPDATE portfolio SET balance=?, open_trades=open_trades+1, total_trades=total_trades+1,
               updated_at=CURRENT_TIMESTAMP WHERE id=(SELECT MAX(id) FROM portfolio)""",
            (new_balance,),
        )
        await self._log("TRADE_OPEN", prediction.city, trade.reasoning)
        logger.info(f"Trade opened: {direction} {prediction.city} ${sizing.position_size:.2f} @ {entry_price:.4f}")
        return trade

    async def check_and_hedge(self, new_prediction: PredictionResult) -> Optional[HedgeEvent]:
        open_trades = await fetch_all(
            "SELECT * FROM trades WHERE city=? AND status='open' ORDER BY created_at DESC",
            (new_prediction.city,),
        )
        if not open_trades:
            return None
        trade_row = open_trades[0]
        original_trade = Trade(**trade_row)
        original_edge = original_trade.edge_at_entry
        new_edge = new_prediction.edge
        if original_trade.direction == "NO":
            new_edge = -new_edge
        edge_shrunk = abs(new_edge) < self.hedge_threshold and abs(original_edge) >= self.hedge_threshold
        edge_flipped = (original_edge > 0 and new_edge < -self.hedge_threshold) or \
                       (original_edge < 0 and new_edge > self.hedge_threshold)
        price_moved = abs(new_prediction.market_probability - original_trade.entry_price) > 0.15
        if not (edge_shrunk or edge_flipped or price_moved):
            return None
        trigger = []
        if edge_shrunk:
            trigger.append(f"edge shrunk below threshold ({new_edge:.4f})")
        if edge_flipped:
            trigger.append(f"edge flipped ({original_edge:.4f} → {new_edge:.4f})")
        if price_moved:
            trigger.append(f"large price move (entry={original_trade.entry_price:.4f}, now={new_prediction.market_probability:.4f})")
        trigger_reason = "; ".join(trigger)
        if edge_flipped:
            return await self._full_hedge(original_trade, new_prediction, trigger_reason)
        else:
            return await self._partial_close(original_trade, new_prediction, trigger_reason)

    async def _full_hedge(self, original: Trade, prediction: PredictionResult,
                          reason: str) -> HedgeEvent:
        exit_price = prediction.market_probability if original.direction == "YES" else (1 - prediction.market_probability)
        pnl = (exit_price - original.entry_price) * original.size
        if original.direction == "NO":
            pnl = (original.entry_price - exit_price) * original.size
        await execute(
            """UPDATE trades SET status='closed', exit_price=?, pnl=?, edge_at_action=?,
               trade_type='hedge', reasoning=reasoning||' | HEDGE: '||?, closed_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (exit_price, round(pnl, 2), prediction.edge, reason, original.id),
        )
        portfolio = await fetch_one("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        new_balance = portfolio["balance"] + original.size + pnl
        wins_delta = 1 if pnl > 0 else 0
        losses_delta = 1 if pnl < 0 else 0
        await execute(
            """UPDATE portfolio SET balance=?, total_pnl=total_pnl+?, open_trades=MAX(0,open_trades-1),
               wins=wins+?, losses=losses+?, updated_at=CURRENT_TIMESTAMP
               WHERE id=(SELECT MAX(id) FROM portfolio)""",
            (round(new_balance, 2), round(pnl, 2), wins_delta, losses_delta),
        )
        await self._log("HEDGE_FULL", original.city, f"Full hedge: {reason}. PnL: ${pnl:.2f}")
        logger.info(f"Full hedge on {original.city}: {reason}. PnL: ${pnl:.2f}")
        return HedgeEvent(
            original_trade=original,
            trigger_reason=reason,
            pre_edge=original.edge_at_entry,
            post_edge=prediction.edge,
            action_taken="full_close_hedge",
        )

    async def _partial_close(self, original: Trade, prediction: PredictionResult,
                             reason: str) -> HedgeEvent:
        close_fraction = 0.5
        close_size = original.size * close_fraction
        remaining_size = original.size - close_size
        exit_price = prediction.market_probability if original.direction == "YES" else (1 - prediction.market_probability)
        pnl = (exit_price - original.entry_price) * close_size
        if original.direction == "NO":
            pnl = (original.entry_price - exit_price) * close_size
        await execute("UPDATE trades SET size=? WHERE id=?", (round(remaining_size, 2), original.id))
        cursor = await execute(
            """INSERT INTO trades (city, trade_type, direction, size, entry_price, exit_price, pnl,
               kelly_fraction, edge_at_entry, edge_at_action, reasoning, parent_trade_id, status, closed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (original.city, "hedge", original.direction, round(close_size, 2), original.entry_price,
             exit_price, round(pnl, 2), original.kelly_fraction, original.edge_at_entry,
             prediction.edge, f"Partial hedge: {reason}", original.id, "closed"),
        )
        portfolio = await fetch_one("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        new_balance = portfolio["balance"] + close_size + pnl
        await execute(
            """UPDATE portfolio SET balance=?, total_pnl=total_pnl+?, total_trades=total_trades+1,
               updated_at=CURRENT_TIMESTAMP WHERE id=(SELECT MAX(id) FROM portfolio)""",
            (round(new_balance, 2), round(pnl, 2)),
        )
        await self._log("HEDGE_PARTIAL", original.city, f"Partial hedge ({close_fraction:.0%}): {reason}. PnL: ${pnl:.2f}")
        logger.info(f"Partial hedge on {original.city}: {reason}. Closed ${close_size:.2f}, PnL: ${pnl:.2f}")
        return HedgeEvent(
            original_trade=original,
            trigger_reason=reason,
            pre_edge=original.edge_at_entry,
            post_edge=prediction.edge,
            action_taken=f"partial_close_{close_fraction:.0%}",
        )

    async def close_trade(self, trade_id: int, exit_price: float) -> Optional[Trade]:
        row = await fetch_one("SELECT * FROM trades WHERE id=? AND status='open'", (trade_id,))
        if not row:
            return None
        trade = Trade(**row)
        pnl = (exit_price - trade.entry_price) * trade.size
        if trade.direction == "NO":
            pnl = (trade.entry_price - exit_price) * trade.size
        await execute(
            """UPDATE trades SET status='closed', exit_price=?, pnl=?, trade_type='close',
               closed_at=CURRENT_TIMESTAMP WHERE id=?""",
            (exit_price, round(pnl, 2), trade_id),
        )
        portfolio = await fetch_one("SELECT * FROM portfolio ORDER BY id DESC LIMIT 1")
        new_balance = portfolio["balance"] + trade.size + pnl
        wins_delta = 1 if pnl > 0 else 0
        losses_delta = 1 if pnl < 0 else 0
        await execute(
            """UPDATE portfolio SET balance=?, total_pnl=total_pnl+?, open_trades=MAX(0,open_trades-1),
               wins=wins+?, losses=losses+?, updated_at=CURRENT_TIMESTAMP
               WHERE id=(SELECT MAX(id) FROM portfolio)""",
            (round(new_balance, 2), round(pnl, 2), wins_delta, losses_delta),
        )
        trade.pnl = round(pnl, 2)
        trade.exit_price = exit_price
        trade.status = "closed"
        await self._log("TRADE_CLOSE", trade.city, f"Closed trade #{trade_id}: PnL ${pnl:.2f}")
        return trade

    async def _log(self, action: str, city: str, message: str):
        await execute(
            "INSERT INTO agent_logs (level, agent, action, message) VALUES (?,?,?,?)",
            ("INFO", "TradingAgent", action, f"[{city}] {message}"),
        )


trading_agent = TradingAgent()
