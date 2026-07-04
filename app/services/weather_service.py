import httpx
import json
from typing import Optional
from app.core.config import get_settings
from app.schemas.weather import WeatherData
from app.database.connection import execute, fetch_one
from loguru import logger

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"
WEATHERAPI_BASE = "https://api.weatherapi.com/v1"


async def fetch_openweather(city_key: str, city_config: dict) -> Optional[WeatherData]:
    settings = get_settings()
    if not settings.openweather_api_key:
        logger.warning("OpenWeather API key not configured, using cache")
        return await _get_cached(city_key, "openweather")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{OPENWEATHER_BASE}/weather",
                params={"q": city_config["name"], "appid": settings.openweather_api_key, "units": "metric"},
            )
            resp.raise_for_status()
            data = resp.json()
            weather = WeatherData(
                city=city_key,
                source="openweather",
                temperature=data["main"]["temp"],
                feels_like=data["main"].get("feels_like"),
                humidity=data["main"].get("humidity"),
                wind_speed=data.get("wind", {}).get("speed"),
                rain_probability=data.get("rain", {}).get("1h", 0) / 100 if "rain" in data else None,
                description=data["weather"][0]["description"] if data.get("weather") else None,
                raw_json=json.dumps(data),
            )
            await _cache_weather(weather)
            return weather
    except Exception as e:
        logger.error(f"OpenWeather fetch failed for {city_key}: {e}")
        return await _get_cached(city_key, "openweather")


async def fetch_openweather_forecast(city_key: str, city_config: dict) -> Optional[WeatherData]:
    settings = get_settings()
    if not settings.openweather_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{OPENWEATHER_BASE}/forecast",
                params={"q": city_config["name"], "appid": settings.openweather_api_key, "units": "metric", "cnt": 8},
            )
            resp.raise_for_status()
            data = resp.json()
            forecasts = data.get("list", [])
            if not forecasts:
                return None
            avg_temp = sum(f["main"]["temp"] for f in forecasts) / len(forecasts)
            avg_humidity = sum(f["main"].get("humidity", 0) for f in forecasts) / len(forecasts)
            rain_count = sum(1 for f in forecasts if f.get("rain"))
            weather = WeatherData(
                city=city_key,
                source="openweather_forecast",
                temperature=round(avg_temp, 1),
                humidity=round(avg_humidity, 1),
                rain_probability=round(rain_count / len(forecasts), 2),
                description=f"24h forecast avg from {len(forecasts)} data points",
                raw_json=json.dumps(data),
            )
            await _cache_weather(weather)
            return weather
    except Exception as e:
        logger.error(f"OpenWeather forecast failed for {city_key}: {e}")
        return None


async def fetch_weatherapi(city_key: str, city_config: dict) -> Optional[WeatherData]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{WEATHERAPI_BASE}/current.json",
                params={"key": "free", "q": f"{city_config['lat']},{city_config['lon']}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                weather = WeatherData(
                    city=city_key,
                    source="weatherapi",
                    temperature=current.get("temp_c"),
                    feels_like=current.get("feelslike_c"),
                    humidity=current.get("humidity"),
                    wind_speed=current.get("wind_kph"),
                    description=current.get("condition", {}).get("text"),
                    raw_json=json.dumps(data),
                )
                await _cache_weather(weather)
                return weather
    except Exception as e:
        logger.warning(f"WeatherAPI fetch failed for {city_key}: {e}")
    return await _get_cached(city_key, "weatherapi")


async def _cache_weather(weather: WeatherData):
    await execute(
        """INSERT INTO weather_cache (city, source, temperature, feels_like, humidity,
           wind_speed, rain_probability, description, raw_json) VALUES (?,?,?,?,?,?,?,?,?)""",
        (weather.city, weather.source, weather.temperature, weather.feels_like,
         weather.humidity, weather.wind_speed, weather.rain_probability,
         weather.description, weather.raw_json),
    )


async def _get_cached(city_key: str, source: str) -> Optional[WeatherData]:
    row = await fetch_one(
        "SELECT * FROM weather_cache WHERE city=? AND source=? ORDER BY fetched_at DESC LIMIT 1",
        (city_key, source),
    )
    if row:
        return WeatherData(**{k: row[k] for k in ["city", "source", "temperature", "feels_like",
                                                    "humidity", "wind_speed", "rain_probability", "description"]})
    return None
