import time
import json
from typing import Optional
from loguru import logger

_memory_cache: dict[str, tuple[str, float]] = {}


def cache_get(key: str) -> Optional[str]:
    entry = _memory_cache.get(key)
    if entry and entry[1] > time.time():
        return entry[0]
    if entry:
        del _memory_cache[key]
    return None


def cache_set(key: str, value: str, ttl_seconds: int = 3600):
    _memory_cache[key] = (value, time.time() + ttl_seconds)


def cache_delete(key: str):
    _memory_cache.pop(key, None)


async def cache_get_with_db(key: str) -> Optional[str]:
    mem = cache_get(key)
    if mem:
        return mem
    try:
        from app.database.connection import fetch_one
        row = await fetch_one(
            "SELECT cache_value, expires_at FROM discovery_cache WHERE cache_key=? AND expires_at > datetime('now')",
            (key,),
        )
        if row:
            cache_set(key, row["cache_value"], 3600)
            return row["cache_value"]
    except Exception as e:
        logger.debug(f"DB cache miss for {key}: {e}")
    return None


async def cache_set_with_db(key: str, value: str, ttl_seconds: int = 3600):
    cache_set(key, value, ttl_seconds)
    try:
        from app.database.connection import execute
        await execute(
            "INSERT OR REPLACE INTO discovery_cache (cache_key, cache_value, expires_at) VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))",
            (key, value, str(ttl_seconds)),
        )
    except Exception as e:
        logger.debug(f"DB cache write failed for {key}: {e}")
