import json
from typing import Optional, List
from app.core.config import get_settings
from app.schemas.weather import WeatherData
from app.database.connection import execute
from loguru import logger


async def fetch_apify_weather(city_key: str, city_config: dict) -> Optional[WeatherData]:
    settings = get_settings()
    if not settings.apify_api_token:
        logger.warning("Apify token not configured, skipping apify/weather-api")
        return None
    try:
        from apify_client import ApifyClient
        client = ApifyClient(settings.apify_api_token)
        run_input = {"locations": [city_config["name"]], "units": "metric"}
        run = client.actor("apify/weather-api").call(run_input=run_input, timeout_secs=30)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            return None
        item = items[0]
        weather = WeatherData(
            city=city_key,
            source="apify_weather_api",
            temperature=item.get("temperature") or item.get("temp"),
            humidity=item.get("humidity"),
            wind_speed=item.get("windSpeed") or item.get("wind_speed"),
            rain_probability=item.get("precipProbability") or item.get("rain_probability"),
            description=item.get("description") or item.get("summary"),
            raw_json=json.dumps(item),
        )
        await _cache(weather)
        logger.info(f"Apify weather-api fetched for {city_key}")
        return weather
    except Exception as e:
        logger.error(f"Apify weather-api failed for {city_key}: {e}")
        return None


async def fetch_apify_scraper(city_key: str, city_config: dict) -> Optional[WeatherData]:
    settings = get_settings()
    if not settings.apify_api_token:
        logger.warning("Apify token not configured, skipping oneary/weather-database-scraper")
        return None
    try:
        from apify_client import ApifyClient
        client = ApifyClient(settings.apify_api_token)
        run_input = {"location": city_config["name"], "country": city_config.get("country", "")}
        run = client.actor("oneary/weather-database-scraper").call(run_input=run_input, timeout_secs=30)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            return None
        item = items[0]
        weather = WeatherData(
            city=city_key,
            source="apify_scraper",
            temperature=item.get("temperature") or item.get("temp"),
            humidity=item.get("humidity"),
            wind_speed=item.get("wind"),
            description=item.get("condition") or item.get("weather"),
            raw_json=json.dumps(item),
        )
        await _cache(weather)
        logger.info(f"Apify scraper fetched for {city_key}")
        return weather
    except Exception as e:
        logger.error(f"Apify scraper failed for {city_key}: {e}")
        return None


async def _cache(weather: WeatherData):
    await execute(
        """INSERT INTO weather_cache (city, source, temperature, feels_like, humidity,
           wind_speed, rain_probability, description, raw_json) VALUES (?,?,?,?,?,?,?,?,?)""",
        (weather.city, weather.source, weather.temperature, weather.feels_like,
         weather.humidity, weather.wind_speed, weather.rain_probability,
         weather.description, weather.raw_json),
    )
