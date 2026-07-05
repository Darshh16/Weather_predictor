from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Dict, List
from functools import lru_cache


class CityConfig:
    CITIES: Dict[str, dict] = {
        "new_york": {"name": "New York", "country": "US", "lat": 40.7128, "lon": -74.0060, "owm_id": 5128581},
        "london": {"name": "London", "country": "GB", "lat": 51.5074, "lon": -0.1278, "owm_id": 2643743},
        "tokyo": {"name": "Tokyo", "country": "JP", "lat": 35.6762, "lon": 139.6503, "owm_id": 1850147},
        "sydney": {"name": "Sydney", "country": "AU", "lat": -33.8688, "lon": 151.2093, "owm_id": 2147714},
        "mumbai": {"name": "Mumbai", "country": "IN", "lat": 19.0760, "lon": 72.8777, "owm_id": 1275339},
    }

    @classmethod
    def get_city_names(cls) -> List[str]:
        return list(cls.CITIES.keys())

    @classmethod
    def get_city(cls, key: str) -> dict:
        return cls.CITIES.get(key, {})


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openweather_api_key: str = ""
    apify_api_token: str = ""

    hermes_base_url: str = "http://localhost:8001/v1"
    hermes_enabled: bool = False

    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    initial_bankroll: float = 10000.0
    hedge_edge_threshold: float = 0.02
    max_kelly_fraction: float = 0.25
    max_exposure_per_market: float = 0.15
    max_portfolio_exposure: float = 0.50

    database_path: str = "data/weather_ai.db"
    log_level: str = "INFO"
    log_path: str = "logs/weather_ai.log"

    @property
    def llm_base_url(self) -> str:
        return self.hermes_base_url if self.hermes_enabled else self.openrouter_base_url

    @property
    def llm_api_key(self) -> str:
        return self.openrouter_api_key

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
