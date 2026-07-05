import json
import httpx
from typing import Optional
from app.core.config import get_settings
from app.schemas.weather import WeatherData
from app.database.connection import execute
from app.services.discovery_cache import cache_get_with_db, cache_set_with_db, cache_delete
from loguru import logger

APIFY_STORE_URL = "https://api.apify.com/v2/store"
APIFY_ACTOR_RUN_URL = "https://api.apify.com/v2/acts/{actor_id}/runs"
CACHE_KEY = "apify_working_actor"
TTL_24H = 86400


async def _search_free_actors(token: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                APIFY_STORE_URL,
                params={"search": "weather", "pricingModel": "FREE", "sortBy": "popularity", "limit": 20},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                logger.warning(f"Apify Store search returned {resp.status_code}")
                return []
            data = resp.json()
            items = data.get("data", {}).get("items", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                items = []
            free = [a for a in items if a.get("currentPricingInfo", {}).get("pricingModel") == "FREE"]
            logger.info(f"Apify Store: found {len(free)} free weather actors out of {len(items)} total")
            return free
    except Exception as e:
        logger.error(f"Apify Store search failed: {e}")
        return []


async def _test_actor(token: str, actor_id: str, city_name: str) -> bool:
    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)
        run_input = {"locations": [city_name], "location": city_name, "query": city_name, "units": "metric"}
        run = client.actor(actor_id).call(run_input=run_input, timeout_secs=30)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items:
            logger.info(f"Apify actor {actor_id} returned {len(items)} items for test city {city_name}")
            return True
        logger.debug(f"Apify actor {actor_id} returned 0 items")
        return False
    except Exception as e:
        logger.debug(f"Apify actor {actor_id} test failed: {e}")
        return False


async def discover_free_actor() -> Optional[str]:
    settings = get_settings()
    if not settings.apify_api_token:
        return None
    cached = await cache_get_with_db(CACHE_KEY)
    if cached:
        return cached
    actors = await _search_free_actors(settings.apify_api_token)
    if not actors:
        logger.warning("No free Apify weather actors found — Apify source will be skipped")
        return None
        
    weather_terms = ["weather", "forecast", "temperature", "climate"]
    filtered_actors = []
    for actor in actors:
        text = (actor.get("title", "") + " " + actor.get("description", "")).lower()
        if any(term in text for term in weather_terms):
            filtered_actors.append(actor)
            
    logger.info(f"Apify Store: filtered to {len(filtered_actors)} relevant weather actors")
    
    tested_count = 0
    for actor in filtered_actors:
        if tested_count >= 3:
            logger.warning("Reached max limit of 3 Apify actor tests. Giving up.")
            break
            
        actor_id = actor.get("id") or actor.get("username", "") + "/" + actor.get("name", "")
        if not actor_id or actor_id == "/":
            continue
            
        tested_count += 1
        logger.info(f"Testing Apify actor: {actor_id} ({actor.get('title', 'untitled')})")
        if await _test_actor(settings.apify_api_token, actor_id, "London"):
            logger.info(f"Auto-discovered working free Apify actor: {actor_id}")
            await cache_set_with_db(CACHE_KEY, actor_id, TTL_24H)
            return actor_id
            
    logger.warning("All free Apify actors failed testing — Apify source will be skipped")
    return None


async def fetch_apify_weather(city_key: str, city_config: dict) -> Optional[WeatherData]:
    settings = get_settings()
    if not settings.apify_api_token:
        return None
    actor_id = await discover_free_actor()
    if not actor_id:
        return None
    try:
        from apify_client import ApifyClient
        client = ApifyClient(settings.apify_api_token)
        city_name = city_config["name"]
        run_input = {"locations": [city_name], "location": city_name, "query": city_name, "units": "metric"}
        run = client.actor(actor_id).call(run_input=run_input, timeout_secs=30)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            return None
        item = items[0]
        weather = WeatherData(
            city=city_key,
            source=f"apify_{actor_id.split('/')[-1]}",
            temperature=item.get("temperature") or item.get("temp") or item.get("temp_c"),
            humidity=item.get("humidity"),
            wind_speed=item.get("windSpeed") or item.get("wind_speed") or item.get("wind"),
            rain_probability=item.get("precipProbability") or item.get("rain_probability"),
            description=item.get("description") or item.get("summary") or item.get("condition") or item.get("weather"),
            raw_json=json.dumps(item),
        )
        await _cache(weather)
        logger.info(f"Apify [{actor_id}] fetched weather for {city_key}")
        return weather
    except Exception as e:
        logger.error(f"Apify actor {actor_id} failed for {city_key}: {e}")
        cache_delete(CACHE_KEY)
        return None


async def _cache(weather: WeatherData):
    await execute(
        """INSERT INTO weather_cache (city, source, temperature, feels_like, humidity,
           wind_speed, rain_probability, description, raw_json) VALUES (?,?,?,?,?,?,?,?,?)""",
        (weather.city, weather.source, weather.temperature, weather.feels_like,
         weather.humidity, weather.wind_speed, weather.rain_probability,
         weather.description, weather.raw_json),
    )
