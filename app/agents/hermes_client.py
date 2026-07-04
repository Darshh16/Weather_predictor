from app.schemas.prediction import PredictionResult
from app.schemas.weather import WeatherReport
from app.schemas.market import MarketSnapshot
from app.services.llm_service import chat_completion, parse_json_response
from app.prompts.prediction_prompt import build_prediction_prompt
from app.database.connection import execute
from loguru import logger


class HermesClient:
    async def predict(self, weather: WeatherReport, market: MarketSnapshot) -> PredictionResult:
        logger.info(f"Generating prediction for {weather.city}")
        messages = build_prediction_prompt(weather, market)
        response = await chat_completion(messages, temperature=0.3, max_tokens=800)
        if response:
            parsed = parse_json_response(response)
            if parsed:
                return await self._build_result(weather, market, parsed, response)
        logger.warning(f"LLM prediction failed for {weather.city}, using heuristic fallback")
        return await self._heuristic_fallback(weather, market)

    async def _build_result(self, weather: WeatherReport, market: MarketSnapshot,
                            parsed: dict, raw: str) -> PredictionResult:
        model_prob = float(parsed.get("probability", parsed.get("model_probability", 0.5)))
        model_prob = max(0.01, min(0.99, model_prob))
        market_prob = market.yes_price
        edge = round(model_prob - market_prob, 4)
        rec = parsed.get("recommendation", "HOLD").upper()
        if rec not in ("BUY YES", "BUY NO", "HOLD"):
            rec = "BUY YES" if edge > 0.02 else ("BUY NO" if edge < -0.02 else "HOLD")
        confidence = float(parsed.get("confidence", 0.5))
        reasoning = parsed.get("reasoning", raw[:500])
        result = PredictionResult(
            city=weather.city,
            model_probability=model_prob,
            market_probability=market_prob,
            edge=edge,
            recommendation=rec,
            reasoning=reasoning,
            confidence=confidence,
            weather_summary=weather.summary,
        )
        await self._persist(result)
        logger.info(f"Prediction for {weather.city}: prob={model_prob}, edge={edge}, rec={rec}")
        return result

    async def _heuristic_fallback(self, weather: WeatherReport, market: MarketSnapshot) -> PredictionResult:
        temp = weather.consensus_temperature or 20
        rain = weather.consensus_rain_prob or 0.3
        conf = weather.validation.confidence_score if weather.validation else 0.3
        model_prob = 0.5 + (temp - 20) * 0.01 + (0.5 - rain) * 0.15
        model_prob = max(0.1, min(0.9, model_prob))
        edge = round(model_prob - market.yes_price, 4)
        rec = "BUY YES" if edge > 0.03 else ("BUY NO" if edge < -0.03 else "HOLD")
        result = PredictionResult(
            city=weather.city,
            model_probability=round(model_prob, 4),
            market_probability=market.yes_price,
            edge=edge,
            recommendation=rec,
            reasoning=f"Heuristic: temp={temp}°C, rain={rain:.0%}, market={market.yes_price}. {weather.summary}",
            confidence=round(conf * 0.7, 2),
            weather_summary=weather.summary,
        )
        await self._persist(result)
        return result

    async def _persist(self, r: PredictionResult) -> int:
        cursor = await execute(
            """INSERT INTO predictions (city, model_probability, market_probability, edge,
               recommendation, reasoning, confidence, weather_summary)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r.city, r.model_probability, r.market_probability, r.edge,
             r.recommendation, r.reasoning, r.confidence, r.weather_summary),
        )
        return cursor.lastrowid


hermes_client = HermesClient()
