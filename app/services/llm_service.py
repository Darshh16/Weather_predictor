import httpx
import json
from typing import Optional
from app.core.config import get_settings
from loguru import logger


async def chat_completion(messages: list, temperature: float = 0.3, max_tokens: int = 1024) -> Optional[str]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://weather-ai-agent.local",
                    "X-Title": "Weather AI Trading Agent",
                },
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"LLM response received ({len(content)} chars)")
            return content
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def parse_json_response(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response")
        return None
