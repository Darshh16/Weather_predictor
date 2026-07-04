import aiosqlite
from pathlib import Path
from app.core.config import get_settings
from loguru import logger

_db = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS weather_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    source TEXT NOT NULL,
    temperature REAL,
    feels_like REAL,
    humidity REAL,
    wind_speed REAL,
    rain_probability REAL,
    description TEXT,
    raw_json TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    contract_id TEXT,
    question TEXT,
    yes_price REAL,
    no_price REAL,
    volume REAL,
    liquidity REAL,
    resolution_date TEXT,
    raw_json TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    model_probability REAL,
    market_probability REAL,
    edge REAL,
    recommendation TEXT,
    reasoning TEXT,
    confidence REAL,
    weather_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    trade_type TEXT NOT NULL DEFAULT 'open',
    direction TEXT NOT NULL,
    size REAL NOT NULL,
    entry_price REAL,
    exit_price REAL,
    pnl REAL DEFAULT 0.0,
    kelly_fraction REAL,
    edge_at_entry REAL,
    edge_at_action REAL,
    reasoning TEXT,
    prediction_id INTEGER,
    parent_trade_id INTEGER,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    FOREIGN KEY (parent_trade_id) REFERENCES trades(id)
);

CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balance REAL NOT NULL,
    equity REAL NOT NULL,
    total_trades INTEGER DEFAULT 0,
    open_trades INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    agent TEXT,
    action TEXT,
    message TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        db_path = get_settings().database_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(db_path)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _db.commit()
        count = await _db.execute("SELECT COUNT(*) FROM portfolio")
        row = await count.fetchone()
        if row[0] == 0:
            await _db.execute(
                "INSERT INTO portfolio (balance, equity) VALUES (?, ?)",
                (get_settings().initial_bankroll, get_settings().initial_bankroll),
            )
            await _db.commit()
        logger.info(f"Database initialized at {db_path}")
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


async def execute(query: str, params: tuple = ()) -> aiosqlite.Cursor:
    db = await get_db()
    cursor = await db.execute(query, params)
    await db.commit()
    return cursor


async def fetch_all(query: str, params: tuple = ()) -> list:
    db = await get_db()
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def fetch_one(query: str, params: tuple = ()) -> dict | None:
    db = await get_db()
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return dict(row) if row else None
