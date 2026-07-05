import httpx
import json
import time
from typing import Optional
from app.core.config import get_settings
from app.services.discovery_cache import cache_get_with_db, cache_set_with_db, cache_delete
from loguru import logger

CACHE_KEY_MODEL = "openrouter_working_model"
CACHE_KEY_MODEL_LIST = "openrouter_free_models"
TTL_12H = 43200


async def discover_free_models() -> list[str]:
    cached = await cache_get_with_db(CACHE_KEY_MODEL_LIST)
    if cached:
        return json.loads(cached)
    settings = get_settings()
    if not settings.openrouter_api_key:
        logger.warning("OpenRouter API key not configured")
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", data) if isinstance(data, dict) else data
            free = []
            
            if models:
                logger.info(f"OpenRouter raw model example: {json.dumps(models[0])}")
                
            for m in models:
                pricing = m.get("pricing", {})
                prompt_cost = str(pricing.get("prompt", "1"))
                completion_cost = str(pricing.get("completion", "1"))
                
                # Check modality
                architecture = m.get("architecture", {})
                modality = str(architecture.get("modality", "text->text")).lower()
                
                if "text" not in modality:
                    continue
                if any(bad in modality.split("->")[-1] for bad in ["audio", "image", "video"]):
                    continue
                    
                if prompt_cost == "0" and completion_cost == "0":
                    free.append({
                        "id": m["id"],
                        "context_length": m.get("context_length", 0),
                        "name": m.get("name", m["id"]),
                    })
            free.sort(key=lambda x: x["context_length"], reverse=True)
            model_ids = [m["id"] for m in free]
            logger.info(f"Auto-discovered {len(model_ids)} free OpenRouter text models")
            for m in free[:5]:
                logger.info(f"  Free model: {m['id']} (context: {m['context_length']})")
            if model_ids:
                await cache_set_with_db(CACHE_KEY_MODEL_LIST, json.dumps(model_ids), TTL_12H)
            return model_ids
    except Exception as e:
        logger.error(f"OpenRouter model discovery failed: {e}")
        return []


async def get_working_model() -> Optional[str]:
    cached = await cache_get_with_db(CACHE_KEY_MODEL)
    if cached:
        return cached
    models = await discover_free_models()
    return models[0] if models else None


async def chat_completion(messages: list, temperature: float = 0.3, max_tokens: int = 1024) -> Optional[str]:
    settings = get_settings()
    models = await discover_free_models()
    last_working = await cache_get_with_db(CACHE_KEY_MODEL)
    if last_working and last_working in models:
        models = [last_working] + [m for m in models if m != last_working]
    elif last_working:
        models = [last_working] + models
    if not models:
        logger.error("No free LLM models available")
        return None
        
    start_time = time.time()
    attempts = 0
    max_attempts = 4
    max_total_time = 15.0
    
    for model_id in models:
        if attempts >= max_attempts:
            logger.warning("Reached max LLM attempts budget")
            break
        if time.time() - start_time > max_total_time:
            logger.warning("Reached max total time for LLM fallback")
            break
            
        attempts += 1
        try:
            # 8 seconds timeout per request
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.llm_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://weather-ai-agent.local",
                        "X-Title": "Weather AI Trading Agent",
                    },
                    json={
                        "model": model_id,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                if resp.status_code in (400, 404, 429, 500, 502, 503):
                    logger.warning(f"LLM model {model_id} returned {resp.status_code}, trying next")
                    continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"LLM response from {model_id} ({len(content)} chars)")
                await cache_set_with_db(CACHE_KEY_MODEL, model_id, TTL_12H)
                return content
        except httpx.HTTPStatusError as e:
            logger.warning(f"LLM model {model_id} HTTP error: {e.response.status_code}")
            continue
        except Exception as e:
            logger.warning(f"LLM model {model_id} failed: {e}")
            continue
            
    logger.error("All attempted free LLM models failed or timed out")
    cache_delete(CACHE_KEY_MODEL)
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
