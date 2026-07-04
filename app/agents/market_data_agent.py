from app.schemas.market import MarketSnapshot
from app.services.polymarket_service import get_market_snapshot
from loguru import logger


class MarketDataAgent:
    async def fetch(self, city_key: str, city_config: dict) -> MarketSnapshot:
        logger.info(f"Fetching market data for {city_config['name']}")
        snapshot = await get_market_snapshot(city_key, city_config)
        logger.info(f"Market data for {city_key}: YES={snapshot.yes_price}, NO={snapshot.no_price}")
        return snapshot

    async def fetch_all(self, cities: dict) -> dict[str, MarketSnapshot]:
        results = {}
        for key, config in cities.items():
            results[key] = await self.fetch(key, config)
        return results


market_data_agent = MarketDataAgent()
