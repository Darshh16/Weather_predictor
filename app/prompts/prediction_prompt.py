from app.schemas.weather import WeatherReport
from app.schemas.market import MarketSnapshot

SYSTEM_PROMPT = """You are a weather prediction analyst for prediction markets.
You analyze weather data from multiple sources and market odds to estimate the true probability of a weather outcome.
You must respond ONLY with valid JSON in this exact format:
{
  "probability": 0.65,
  "recommendation": "BUY YES",
  "confidence": 0.75,
  "reasoning": "Your detailed reasoning here"
}
Rules:
- probability must be between 0.01 and 0.99
- recommendation must be exactly one of: "BUY YES", "BUY NO", "HOLD"
- confidence must be between 0 and 1
- reasoning should explain your analysis in 2-3 sentences
- Compare your estimated probability to the market price to identify edge
- Consider source agreement/disagreement in your confidence"""


def build_prediction_prompt(weather: WeatherReport, market: MarketSnapshot) -> list:
    sources_text = ""
    for s in weather.sources:
        sources_text += f"\n- {s.source}: temp={s.temperature}°C, humidity={s.humidity}%, "
        sources_text += f"wind={s.wind_speed}, rain_prob={s.rain_probability}, desc={s.description}"
    user_content = f"""Analyze this weather data and market odds for {weather.city}:

WEATHER DATA ({len(weather.sources)} sources):
{sources_text}

CONSENSUS:
- Temperature: {weather.consensus_temperature}°C
- Rain probability: {weather.consensus_rain_prob}
- Wind: {weather.consensus_wind} km/h
- Humidity: {weather.consensus_humidity}%
- Source confidence: {weather.validation.confidence_score if weather.validation else 'N/A'}
- Conflicts: {weather.validation.conflict_detected if weather.validation else False}

MARKET DATA:
- Contract: {market.question or 'Weather outcome prediction'}
- YES price: {market.yes_price} (implied probability: {market.yes_price:.1%})
- NO price: {market.no_price}
- Volume: ${market.volume:,.0f}
- Liquidity: ${market.liquidity:,.0f}

What is the TRUE probability of the YES outcome? Compare it to the market's {market.yes_price:.1%} implied probability.
Respond with JSON only."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
