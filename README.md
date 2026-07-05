# Weather AI Multi-Agent Prediction & Paper Trading Platform

AI-powered weather prediction and paper trading platform for Polymarket weather contracts. Uses multi-agent architecture with Hermes Agent as external reasoning engine, Kelly Criterion for position sizing, and automated hedging.

## Architecture

```
FastAPI App                          Hermes Agent / OpenRouter
------------                         -------------------------
Research Agent  ---weather+market-->  /v1/chat/completions
  (5 sources)                         (LLM reasoning)
      |
Prediction  <---probability, reasoning, recommendation---
      |
Risk Agent (Kelly Criterion, pure math)
      |
Trading Agent (paper trade + hedge logic)
      |
SQLite / DuckDB --> Dashboard (Jinja2 + HTMX + TailwindCSS)
```

## Features

- **6 AI Agents**: Research, Market Data, Hermes Prediction, Risk, Trading, Portfolio
- **5 Cities**: New York, London, Tokyo, Sydney, Mumbai (config-driven, easily extensible)
- **Multi-Source Weather**: OpenWeather + WeatherAPI + Apify actors
- **Live Market Data**: Polymarket Gamma API (public, no auth needed)
- **Kelly Criterion**: Half-Kelly sizing with exposure caps
- **Automated Hedging**: Triggers on edge shrink, flip, or price moves
- **Real-Time Dashboard**: HTMX auto-refresh, glassmorphism dark theme
- **Dual Database**: SQLite (transactional) + DuckDB (analytics)

## Quick Start

```bash
# 1. Clone & enter
cd weather_ai_project

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your API keys

# 5. Run
uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/dashboard

## API Keys Required

| Key | Source | Required |
|-----|--------|----------|
| OPENROUTER_API_KEY | https://openrouter.ai | Yes (free tier) |
| OPENWEATHER_API_KEY | https://openweathermap.org | Yes (free tier) |
| APIFY_API_TOKEN | https://apify.com | Optional |

## Hermes Agent Setup

The system calls Hermes Agent via its OpenAI-compatible API. Two modes:

1. **OpenRouter fallback** (default): Set `HERMES_ENABLED=false` in `.env`. Uses `meta-llama/llama-3.1-8b-instruct:free` via OpenRouter.
2. **Local Hermes sidecar**: Run `docker-compose up` to start both the app and Hermes Agent. Set `HERMES_ENABLED=true`.

No code changes needed to switch — same interface, different backend.

## Configuration Notes

`HEDGE_EDGE_THRESHOLD` is configurable; default is 0.02 (conservative — only hedges when edge nearly vanishes or reverses). For demonstration purposes in the video, this was temporarily raised to make hedge behavior observable within a single session, since real edge decay would normally take multiple days/predictions to cross a 2% threshold.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /dashboard | Main dashboard |
| GET | /markets | Market cards per city |
| GET | /portfolio | Portfolio & positions |
| GET | /analytics | Performance charts |
| GET | /prediction/{city} | Prediction detail |
| POST | /predict | Trigger prediction |
| POST | /trade | Execute paper trade |
| POST | /hedge | Check hedge on position |
| POST | /refresh | Refresh all cities |

## Scaling

Adding a new city requires **only a config entry** in `app/core/config.py`:

```python
"berlin": {"name": "Berlin", "country": "DE", "lat": 52.52, "lon": 13.405, "owm_id": 2950159}
```

No code changes. All agents are city-agnostic.

## Testing

```bash
python tests/test_kelly.py
python tests/test_hedge.py
python tests/test_agents.py
```

## Tech Stack

FastAPI · Jinja2 · HTMX · TailwindCSS · OpenRouter · Hermes Agent · OpenWeather · Apify · Polymarket · SQLite · DuckDB · Pandas · Loguru · Pydantic
