import asyncio
from typing import Optional
from app.core.config import CityConfig
from app.schemas.weather import WeatherData, WeatherReport, SourceValidation
from app.schemas.market import MarketSnapshot
from app.services.weather_service import fetch_openweather, fetch_openweather_forecast, fetch_weatherapi
from app.services.apify_service import fetch_apify_weather, fetch_apify_scraper
from app.agents.market_data_agent import MarketDataAgent
from loguru import logger


class ResearchAgent:
    def __init__(self):
        self.market_agent = MarketDataAgent()

    async def research(self, city_key: str) -> dict:
        city_config = CityConfig.get_city(city_key)
        if not city_config:
            return {"error": f"Unknown city: {city_key}"}
        logger.info(f"Research started for {city_config['name']}")
        weather_tasks = [
            fetch_openweather(city_key, city_config),
            fetch_openweather_forecast(city_key, city_config),
            fetch_weatherapi(city_key, city_config),
            fetch_apify_weather(city_key, city_config),
            fetch_apify_scraper(city_key, city_config),
        ]
        results = await asyncio.gather(*weather_tasks, return_exceptions=True)
        sources = [r for r in results if isinstance(r, WeatherData)]
        validation = self._validate_sources(sources)
        weather_report = WeatherReport(
            city=city_key,
            sources=sources,
            validation=validation,
            consensus_temperature=validation.consensus_temperature,
            consensus_rain_prob=validation.consensus_rain_prob,
            consensus_wind=self._avg([s.wind_speed for s in sources]),
            consensus_humidity=self._avg([s.humidity for s in sources]),
            summary=self._build_summary(city_config, sources, validation),
        )
        market = await self.market_agent.fetch(city_key, city_config)
        logger.info(f"Research complete for {city_config['name']}: {len(sources)} sources, market yes={market.yes_price}")
        return {"weather": weather_report, "market": market, "city": city_key, "city_config": city_config}

    def _validate_sources(self, sources: list[WeatherData]) -> SourceValidation:
        if not sources:
            return SourceValidation(sources_count=0, confidence_score=0)
        temps = [s.temperature for s in sources if s.temperature is not None]
        rains = [s.rain_probability for s in sources if s.rain_probability is not None]
        avg_temp = sum(temps) / len(temps) if temps else None
        spread = max(temps) - min(temps) if len(temps) > 1 else 0
        avg_rain = sum(rains) / len(rains) if rains else None
        conflict = spread > 5.0
        confidence = max(0, min(1.0, 1.0 - (spread / 20.0))) * (len(sources) / 5.0)
        confidence = min(confidence, 1.0)
        notes = []
        if conflict:
            notes.append(f"Temperature spread of {spread:.1f}°C detected across sources")
        if len(sources) < 2:
            notes.append("Limited sources available — lower confidence")
        return SourceValidation(
            sources_count=len(sources),
            consensus_temperature=round(avg_temp, 1) if avg_temp else None,
            temperature_spread=round(spread, 1),
            consensus_rain_prob=round(avg_rain, 2) if avg_rain else None,
            conflict_detected=conflict,
            confidence_score=round(confidence, 2),
            notes=notes,
        )

    def _avg(self, values: list) -> Optional[float]:
        valid = [v for v in values if v is not None]
        return round(sum(valid) / len(valid), 1) if valid else None

    def _build_summary(self, city_config: dict, sources: list, validation: SourceValidation) -> str:
        parts = [f"Weather for {city_config['name']} from {len(sources)} sources."]
        if validation.consensus_temperature:
            parts.append(f"Temperature: {validation.consensus_temperature}°C.")
        if validation.consensus_rain_prob is not None:
            parts.append(f"Rain probability: {validation.consensus_rain_prob*100:.0f}%.")
        if validation.conflict_detected:
            parts.append("WARNING: source conflict detected.")
        parts.append(f"Confidence: {validation.confidence_score:.0%}.")
        return " ".join(parts)


research_agent = ResearchAgent()
