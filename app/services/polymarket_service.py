import httpx
import json
from typing import Optional, List
from app.schemas.market import MarketSnapshot
from app.database.connection import execute, fetch_one
from app.services.discovery_cache import cache_get_with_db, cache_set_with_db
from loguru import logger

GAMMA_API = "https://gamma-api.polymarket.com"
WEATHER_KEYWORDS = ["weather", "temperature", "rain", "snow", "heat", "cold", "storm", "hurricane", "tornado", "celsius", "fahrenheit"]
CACHE_KEY_PREFIX = "polymarket_city_"
CACHE_KEY_MARKETS = "polymarket_weather_markets"
TTL_6H = 21600


async def _fetch_weather_markets() -> list[dict]:
    cached = await cache_get_with_db(CACHE_KEY_MARKETS)
    if cached:
        return json.loads(cached)
    all_markets = []
    
    attempts = 0
    max_attempts = 2
    
    try:
        timeout = httpx.Timeout(8.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for endpoint, params in [
                ("/events", {"tag": "weather", "limit": 100, "active": "true", "closed": "false"}),
                ("/events", {"tag_slug": "weather", "limit": 100, "active": "true", "closed": "false"}),
                ("/events", {"category": "weather", "limit": 100, "active": "true", "closed": "false"}),
                ("/events", {"limit": 100, "active": "true", "closed": "false"}),
            ]:
                if attempts >= max_attempts:
                    logger.warning("Reached max Polymarket fetch attempts (2). Giving up.")
                    break
                attempts += 1
                try:
                    resp = await client.get(f"{GAMMA_API}{endpoint}", params=params)
                    logger.debug(f"Polymarket API request: {endpoint} {params} -> {resp.status_code}")
                    if resp.status_code != 200:
                        logger.warning(f"Polymarket query failed. Status: {resp.status_code}, Body: {resp.text[:500]}")
                        continue
                    data = resp.json()
                    items = data if isinstance(data, list) else data.get("data", data.get("events", data.get("markets", [])))
                    if not isinstance(items, list):
                        logger.warning(f"Polymarket response items not a list: {str(items)[:200]}")
                        continue
                    logger.info(f"Polymarket API returned {len(items)} items for {endpoint} with {params}")
                    for item in items:
                        if "markets" in item and isinstance(item["markets"], list):
                            all_markets.extend(item["markets"])
                        else:
                            all_markets.append(item)
                    if all_markets:
                        break
                except Exception as e:
                    logger.error(f"Error querying Polymarket endpoint {endpoint}: {type(e).__name__}: {e!r}")
                    continue
    except Exception as e:
        logger.error(f"Polymarket API error: {type(e).__name__}: {e!r}")
    
    logger.info(f"Polymarket API total raw markets extracted before filtering: {len(all_markets)}")
    weather_markets = []
    for m in all_markets:
        text = (m.get("question", "") + " " + m.get("title", "") + " " + m.get("description", "") + " " + m.get("series", "") + " " + m.get("category", "")).lower()
        if any(kw in text for kw in WEATHER_KEYWORDS):
            weather_markets.append(m)
    if not weather_markets:
        weather_markets = all_markets
    logger.info(f"Polymarket: discovered {len(weather_markets)} weather-related markets")
    if weather_markets:
        await cache_set_with_db(CACHE_KEY_MARKETS, json.dumps(weather_markets[:50]), TTL_6H)
    return weather_markets


async def get_market_snapshot(city_key: str, city_config: dict) -> MarketSnapshot:
    cached_id = await cache_get_with_db(f"{CACHE_KEY_PREFIX}{city_key}")
    if cached_id:
        markets = await _fetch_weather_markets()
        matched = next((m for m in markets if str(m.get("id", "")) == cached_id or str(m.get("conditionId", "")) == cached_id), None)
        if matched:
            return await _build_live_snapshot(city_key, matched)
    try:
        markets = await _fetch_weather_markets()
        city_name = city_config["name"].lower()
        matched = None
        for m in markets:
            q = (m.get("question", "") + " " + m.get("title", "") + " " + m.get("description", "")).lower()
            if city_name in q or city_key.replace("_", " ") in q:
                matched = m
                break
        if matched:
            mid = str(matched.get("id", matched.get("conditionId", "")))
            await cache_set_with_db(f"{CACHE_KEY_PREFIX}{city_key}", mid, TTL_6H)
            return await _build_live_snapshot(city_key, matched)
    except Exception as e:
        logger.error(f"Polymarket snapshot failed for {city_key}: {e}")
    cached = await _get_cached_snapshot(city_key)
    if cached:
        return cached
    return _generate_synthetic_snapshot(city_key, city_config)


async def _build_live_snapshot(city_key: str, matched: dict) -> MarketSnapshot:
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
        data_source="live",
        raw_json=json.dumps(matched),
    )
    await _cache_snapshot(snapshot)
    logger.info(f"Polymarket LIVE snapshot for {city_key}: YES={yes_price}, NO={no_price}")
    return snapshot


def _generate_synthetic_snapshot(city_key: str, city_config: dict) -> MarketSnapshot:
    import random
    random.seed(hash(city_key) % 1000)
    yes_price = round(random.uniform(0.30, 0.75), 2)
    logger.info(f"Polymarket SIMULATED snapshot for {city_key}: YES={yes_price}")
    return MarketSnapshot(
        city=city_key,
        contract_id=f"synthetic_{city_key}",
        question=f"Will {city_config['name']} temperature exceed seasonal average tomorrow?",
        yes_price=yes_price,
        no_price=round(1.0 - yes_price, 2),
        volume=round(random.uniform(5000, 50000), 2),
        liquidity=round(random.uniform(1000, 20000), 2),
        resolution_date="",
        data_source="simulated",
    )


async def _cache_snapshot(snapshot: MarketSnapshot):
    await execute(
        """INSERT INTO market_snapshots (city, contract_id, question, yes_price, no_price,
           volume, liquidity, resolution_date, data_source, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (snapshot.city, snapshot.contract_id, snapshot.question, snapshot.yes_price,
         snapshot.no_price, snapshot.volume, snapshot.liquidity,
         snapshot.resolution_date, snapshot.data_source, snapshot.raw_json),
    )


async def _get_cached_snapshot(city_key: str) -> Optional[MarketSnapshot]:
    row = await fetch_one(
        "SELECT * FROM market_snapshots WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (city_key,)
    )
    if row:
        return MarketSnapshot(**{k: row[k] for k in ["city", "contract_id", "question", "yes_price",
                                                      "no_price", "volume", "liquidity", "resolution_date", "data_source"]})
    return None
