import asyncio
import functools
from datetime import datetime, timezone


def retry_async(max_retries=3, delay=1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
            raise last_error
        return wrapper
    return decorator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_currency(value: float) -> str:
    if value >= 0:
        return f"${value:,.2f}"
    return f"-${abs(value):,.2f}"


def format_percent(value: float) -> str:
    return f"{value*100:+.2f}%"


def compute_edge(model_prob: float, market_prob: float) -> float:
    return round(model_prob - market_prob, 4)


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default
