import duckdb
import pandas as pd
from app.core.config import get_settings
from loguru import logger


class AnalyticsEngine:
    def __init__(self):
        self.db_path = get_settings().database_path

    def _connect(self):
        conn = duckdb.connect()
        conn.execute(f"ATTACH '{self.db_path}' AS sqlite_db (TYPE SQLITE, READ_ONLY)")
        return conn

    def prediction_accuracy(self) -> dict:
        try:
            conn = self._connect()
            df = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    AVG(CASE WHEN edge > 0 THEN 1.0 ELSE 0.0 END) as avg_positive_edge,
                    AVG(confidence) as avg_confidence,
                    AVG(ABS(edge)) as avg_edge_magnitude
                FROM sqlite_db.predictions
            """).fetchdf()
            conn.close()
            if df.empty or df["total"].iloc[0] == 0:
                return {"total": 0, "avg_positive_edge": 0, "avg_confidence": 0, "avg_edge_magnitude": 0}
            return df.iloc[0].to_dict()
        except Exception as e:
            logger.error(f"Analytics error (prediction_accuracy): {e}")
            return {"total": 0, "avg_positive_edge": 0, "avg_confidence": 0, "avg_edge_magnitude": 0}

    def trading_performance(self) -> dict:
        try:
            conn = self._connect()
            df = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as resolved_trades,
                    SUM(CASE WHEN status = 'closed' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status = 'closed' AND pnl < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN status = 'closed' THEN pnl ELSE 0 END) as total_pnl,
                    AVG(CASE WHEN status = 'closed' THEN pnl ELSE NULL END) as avg_pnl,
                    MAX(CASE WHEN status = 'closed' THEN pnl ELSE NULL END) as best_trade,
                    MIN(CASE WHEN status = 'closed' THEN pnl ELSE NULL END) as worst_trade,
                    AVG(CASE WHEN status = 'closed' THEN kelly_fraction ELSE NULL END) as avg_kelly_utilization
                FROM sqlite_db.trades
            """).fetchdf()
            conn.close()
            if df.empty or df["total_trades"].iloc[0] == 0:
                return {"total_trades": 0, "resolved_trades": 0, "wins": 0, "losses": 0, "total_pnl": 0,
                        "avg_pnl": 0, "best_trade": 0, "worst_trade": 0, "avg_kelly_utilization": 0, "win_rate": 0, "roi": 0}
            
            result = df.fillna(0).iloc[0].to_dict()
            from app.utils.metrics import calculate_win_rate
            result["win_rate"] = calculate_win_rate(result.get("wins") or 0, result.get("losses") or 0)
            result["roi"] = (result.get("total_pnl") or 0) / get_settings().initial_bankroll * 100
            return result
        except Exception as e:
            logger.error(f"Analytics error (trading_performance): {e}")
            return {"total_trades": 0, "resolved_trades": 0, "wins": 0, "losses": 0, "total_pnl": 0,
                    "avg_pnl": 0, "best_trade": 0, "worst_trade": 0, "avg_kelly_utilization": 0, "win_rate": 0, "roi": 0}

    def hedge_effectiveness(self) -> dict:
        try:
            conn = self._connect()
            df = conn.execute("""
                SELECT
                    COUNT(*) as total_hedges,
                    SUM(pnl) as hedge_pnl,
                    AVG(ABS(edge_at_entry - edge_at_action)) as avg_edge_change
                FROM sqlite_db.trades WHERE trade_type = 'hedge'
            """).fetchdf()
            conn.close()
            if df.empty or df["total_hedges"].iloc[0] == 0:
                return {"total_hedges": 0, "hedge_pnl": 0, "avg_edge_change": 0, "pnl_saved_estimate": 0}
            result = df.iloc[0].to_dict()
            result["pnl_saved_estimate"] = abs(result.get("hedge_pnl", 0)) * 0.5
            return result
        except Exception as e:
            logger.error(f"Analytics error (hedge_effectiveness): {e}")
            return {"total_hedges": 0, "hedge_pnl": 0, "avg_edge_change": 0, "pnl_saved_estimate": 0}

    def daily_performance(self) -> list:
        try:
            conn = self._connect()
            df = conn.execute("""
                SELECT
                    CAST(DATE(created_at) AS VARCHAR) as date,
                    COUNT(*) as trades,
                    SUM(pnl) as daily_pnl,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as daily_wins
                FROM sqlite_db.trades
                WHERE status = 'closed'
                GROUP BY DATE(created_at)
                ORDER BY date
            """).fetchdf()
            conn.close()
            return df.to_dict("records") if not df.empty else []
        except Exception as e:
            logger.error(f"Analytics error (daily_performance): {e}")
            return []

    def city_breakdown(self) -> list:
        try:
            conn = self._connect()
            df = conn.execute("""
                SELECT
                    city,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN status = 'closed' THEN pnl ELSE 0 END) as total_pnl,
                    AVG(CASE WHEN status = 'closed' THEN pnl ELSE NULL END) as avg_pnl,
                    SUM(CASE WHEN trade_type = 'hedge' THEN 1 ELSE 0 END) as hedges
                FROM sqlite_db.trades
                GROUP BY city
            """).fetchdf()
            conn.close()
            return df.fillna(0).to_dict("records") if not df.empty else []
        except Exception as e:
            logger.error(f"Analytics error (city_breakdown): {e}")
            return []

    def get_full_report(self) -> dict:
        return {
            "prediction_accuracy": self.prediction_accuracy(),
            "trading_performance": self.trading_performance(),
            "hedge_effectiveness": self.hedge_effectiveness(),
            "daily_performance": self.daily_performance(),
            "city_breakdown": self.city_breakdown(),
        }


analytics_engine = AnalyticsEngine()
