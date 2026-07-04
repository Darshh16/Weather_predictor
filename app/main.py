from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from app.core.logging import setup_logging
from app.database.connection import get_db, close_db
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    await get_db()
    logger.info("Weather AI Trading Platform started")
    yield
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Weather AI Trading Platform",
    description="AI-powered weather prediction & paper trading for Polymarket",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

from app.api.routes import router
app.include_router(router)
