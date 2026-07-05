from loguru import logger
from app.core.config import get_settings
import sys


def setup_logging():
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - {message}",
    )
    logger.add(
        settings.log_path,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
        serialize=True,
    )
    return logger