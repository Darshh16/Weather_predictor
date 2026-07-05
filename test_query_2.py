import duckdb
conn = duckdb.connect()
conn.execute("ATTACH 'data/weather_ai.db' AS sqlite_db (TYPE SQLITE, READ_ONLY)")

try:
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
    print("trading_performance:")
    print(df.fillna(0).to_dict('records'))
except Exception as e:
    print(f"trading_performance Error: {e}")
