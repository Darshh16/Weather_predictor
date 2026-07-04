from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WeatherData(BaseModel):
    city: str
    source: str
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    rain_probability: Optional[float] = None
    description: Optional[str] = None
    raw_json: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class SourceValidation(BaseModel):
    sources_count: int = 0
    consensus_temperature: Optional[float] = None
    temperature_spread: float = 0.0
    consensus_rain_prob: Optional[float] = None
    conflict_detected: bool = False
    confidence_score: float = 0.0
    notes: List[str] = Field(default_factory=list)


class WeatherReport(BaseModel):
    city: str
    sources: List[WeatherData] = Field(default_factory=list)
    validation: Optional[SourceValidation] = None
    consensus_temperature: Optional[float] = None
    consensus_rain_prob: Optional[float] = None
    consensus_wind: Optional[float] = None
    consensus_humidity: Optional[float] = None
    summary: str = ""
