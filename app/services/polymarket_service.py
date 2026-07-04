import httpx
import json
from typing import Optional, List
from app.schemas.market import MarketSnapshot
from app.database.connection import execute, fetch_one
from loguru import logger

GAMMA_API = "https://gamma-api.polymarket.com"


async def search_weather_markets() -> List[dict]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{GAMMA_API}/markets", params={"tag": "weather", "limit": 50})
            if resp.status_code != 200:
                resp = await client.get(f"{GAMMA_API}/markets", params={"tag_slug": "weather", "limit": 50})
            if resp.status_code != 200:
                resp = await client.get(f"{GAMMA_API}/events", params={"tag": "weather", "limit": 50})
            if resp.status_code == 200:
                data = resp.json()
                markets = data if isinstance(data, list) else data.get("data", data.get("markets", []))
                logger.info(f"Found {len(markets)} weather markets on Polymarket")
                return markets
    except Exception as e:
        logger.error(f"Polymarket search failed: {e}")
    return []


async def get_market_snapshot(city_key: str, city_config: dict) -> MarketSnapshot:
    try:
        markets = await search_weather_markets()
        city_name = city_config["name"].lower()
        matched = None
        for m in markets:
            q = (m.get("question", "") + m.get("title", "") + m.get("description", "")).lower()
            if city_name in q or city_key in q:
                matched = m
                break
        if matched:
            outcomes = matched.get("outcomes", [])
            yes_price = no_price = 0.5
            if isinstance(outcomes, list) and len(outcomes) >= 2:
                prices = matched.get("outcomePrices", matched.get("outcome_prices", []))
                if prices and len(prices) >= 2:
                    yes_price = float(prices[0]) if prices[0] else 0.5
                    no_price = float(prices[1]) if prices[1] else 0.5
            elif matched.get("bestAsk") or matched.get("best_ask"):
                yes_price = float(matched.get("bestAsk", matched.get("best_ask", 0.5)))
                no_price = 1.0 - yes_price
            snapshot = MarketSnapshot(
                city=city_key,
                contract_id=str(matched.get("id", matched.get("conditionId", ""))),
                question=matched.get("question", matched.get("title", "")),
                yes_price=yes_price,
                no_price=no_price,
                volume=float(matched.get("volume", matched.get("volumeNum", 0))),
                liquidity=float(matched.get("liquidity", matched.get("liquidityNum", 0))),
                resolution_date=matched.get("endDate", matched.get("end_date_iso", "")),
                raw_json=json.dumps(matched),
            )
            await _cache_snapshot(snapshot)
            return snapshot
    except Exception as e:
        logger.error(f"Polymarket snapshot failed for {city_key}: {e}")
    cached = await _get_cached_snapshot(city_key)
    if cached:
        return cached
    return _generate_synthetic_snapshot(city_key, city_config)


def _generate_synthetic_snapshot(city_key: str, city_config: dict) -> MarketSnapshot:
    import random
    random.seed(hash(city_key) % 1000)
    yes_price = round(random.uniform(0.30, 0.75), 2)
    return MarketSnapshot(
        city=city_key,
        contract_id=f"synthetic_{city_key}",
        question=f"Will {city_config['name']} temperature exceed seasonal average tomorrow?",
        yes_price=yes_price,
        no_price=round(1.0 - yes_price, 2),
        volume=round(random.uniform(5000, 50000), 2),
        liquidity=round(random.uniform(1000, 20000), 2),
        resolution_date="",
    )


async def _cache_snapshot(snapshot: MarketSnapshot):
    await execute(
        """INSERT INTO market_snapshots (city, contract_id, question, yes_price, no_price,
           volume, liquidity, resolution_date, raw_json) VALUES (?,?,?,?,?,?,?,?,?)""",
        (snapshot.city, snapshot.contract_id, snapshot.question, snapshot.yes_price,
         snapshot.no_price, snapshot.volume, snapshot.liquidity,
         snapshot.resolution_date, snapshot.raw_json),
    )


async def _get_cached_snapshot(city_key: str) -> Optional[MarketSnapshot]:
    row = await fetch_one(
        "SELECT * FROM market_snapshots WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (city_key,)
    )
    if row:
        return MarketSnapshot(**{k: row[k] for k in ["city", "contract_id", "question", "yes_price",
                                                      "no_price", "volume", "liquidity", "resolution_date"]})
    return None
