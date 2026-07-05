import duckdb
conn = duckdb.connect()
conn.execute("ATTACH 'data/weather_ai.db' AS sqlite_db (TYPE SQLITE, READ_ONLY)")

try:
    df = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM sqlite_db.trades) as total_trades,
            COUNT(*) as resolved_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl) as total_pnl,
            AVG(pnl) as avg_pnl,
            MAX(pnl) as best_trade,
            MIN(pnl) as worst_trade,
            AVG(kelly_fraction) as avg_kelly_utilization
        FROM sqlite_db.trades WHERE status = 'closed'
    """).fetchdf()
    print("trading_performance:")
    print(df.to_dict('records'))
except Exception as e:
    print(f"trading_performance Error: {e}")

try:
    df = conn.execute("""
        SELECT
            COUNT(*) as total,
            AVG(CASE WHEN edge > 0 THEN 1.0 ELSE 0.0 END) as avg_positive_edge,
            AVG(confidence) as avg_confidence,
            AVG(ABS(edge)) as avg_edge_magnitude
        FROM sqlite_db.predictions
    """).fetchdf()
    print("prediction_accuracy:")
    print(df.to_dict('records'))
except Exception as e:
    print(f"prediction_accuracy Error: {e}")
