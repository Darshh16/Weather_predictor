from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.config import CityConfig, get_settings
from app.agents.research_agent import research_agent
from app.agents.hermes_client import hermes_client
from app.agents.risk_agent import risk_agent
from app.agents.trading_agent import trading_agent
from app.agents.portfolio_agent import portfolio_agent
from app.database.connection import fetch_all, fetch_one, execute
from app.database.analytics import analytics_engine
from loguru import logger

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    state = await portfolio_agent.get_state()
    recent_logs = await fetch_all("SELECT * FROM agent_logs ORDER BY created_at DESC LIMIT 15")
    cities = CityConfig.CITIES
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request, "portfolio": state, "logs": recent_logs,
        "cities": cities, "page": "dashboard",
    })


@router.get("/markets", response_class=HTMLResponse)
async def markets(request: Request):
    cities = CityConfig.CITIES
    market_data = {}
    predictions = {}
    for key in cities:
        snap = await fetch_one(
            "SELECT * FROM market_snapshots WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (key,)
        )
        market_data[key] = snap
        pred = await fetch_one(
            "SELECT * FROM predictions WHERE city=? ORDER BY created_at DESC LIMIT 1", (key,)
        )
        predictions[key] = pred
    return templates.TemplateResponse(request=request, name="markets.html", context={
        "request": request, "cities": cities, "market_data": market_data,
        "predictions": predictions, "page": "markets",
    })


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    state = await portfolio_agent.get_state()
    return templates.TemplateResponse(request=request, name="portfolio.html", context={
        "request": request, "portfolio": state, "page": "portfolio",
    })


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    report = analytics_engine.get_full_report()
    return templates.TemplateResponse(request=request, name="analytics.html", context={
        "request": request, "report": report, "page": "analytics",
    })


@router.get("/prediction/{city}", response_class=HTMLResponse)
async def prediction_detail(request: Request, city: str):
    city_config = CityConfig.get_city(city)
    if not city_config:
        return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "request": request, "error": f"Unknown city: {city}", "page": "dashboard",
            "portfolio": await portfolio_agent.get_state(), "logs": [], "cities": CityConfig.CITIES,
        })
    pred = await fetch_one("SELECT * FROM predictions WHERE city=? ORDER BY created_at DESC LIMIT 1", (city,))
    weather_sources = await fetch_all(
        "SELECT * FROM weather_cache WHERE city=? ORDER BY fetched_at DESC LIMIT 10", (city,)
    )
    market = await fetch_one("SELECT * FROM market_snapshots WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (city,))
    trades = await fetch_all("SELECT * FROM trades WHERE city=? ORDER BY created_at DESC LIMIT 10", (city,))
    return templates.TemplateResponse(request=request, name="prediction.html", context={
        "request": request, "city": city, "city_config": city_config,
        "prediction": pred, "weather_sources": weather_sources,
        "market": market, "trades": trades, "page": "prediction",
    })


@router.post("/predict", response_class=HTMLResponse)
async def predict(request: Request, city: str = Form(...)):
    logger.info(f"Prediction pipeline triggered for {city}")
    try:
        report = await research_agent.research(city)
        if "error" in report:
            return HTMLResponse(f'<div class="text-red-400 p-4">{report["error"]}</div>')
        prediction = await hermes_client.predict(report["weather"], report["market"])
        state = await portfolio_agent.get_state()
        sizing = risk_agent.compute_kelly(prediction, state.balance)
        result_html = f"""
        <div class="bg-gray-800/60 backdrop-blur rounded-xl p-6 border border-gray-700/50 space-y-3">
            <h3 class="text-lg font-semibold text-white">{CityConfig.get_city(city).get('name', city)}</h3>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div><span class="text-gray-400">Model Prob:</span>
                    <span class="text-white font-mono">{prediction.model_probability:.1%}</span></div>
                <div><span class="text-gray-400">Market Prob:</span>
                    <span class="text-white font-mono">{prediction.market_probability:.1%}</span></div>
                <div><span class="text-gray-400">Edge:</span>
                    <span class="{'text-emerald-400' if prediction.edge > 0 else 'text-red-400'} font-mono">
                    {prediction.edge:+.2%}</span></div>
                <div><span class="text-gray-400">Recommendation:</span>
                    <span class="font-bold {'text-emerald-400' if 'YES' in prediction.recommendation else 'text-amber-400' if 'HOLD' in prediction.recommendation else 'text-red-400'}">
                    {prediction.recommendation}</span></div>
                <div><span class="text-gray-400">Confidence:</span>
                    <span class="text-white">{prediction.confidence:.0%}</span></div>
                <div><span class="text-gray-400">Kelly Size:</span>
                    <span class="text-white">${sizing.position_size:.2f} ({sizing.fraction:.1%})</span></div>
            </div>
            <p class="text-gray-300 text-sm mt-2">{prediction.reasoning[:300]}</p>
            <form hx-post="/trade" hx-target="#trade-result-{city}" hx-swap="innerHTML" class="mt-3">
                <input type="hidden" name="city" value="{city}">
                <button type="submit"
                    class="px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-lg
                    hover:from-emerald-400 hover:to-teal-400 transition-all duration-200 text-sm font-medium
                    disabled:opacity-50" {'disabled' if prediction.recommendation == 'HOLD' else ''}>
                    Execute Trade
                </button>
            </form>
            <div id="trade-result-{city}"></div>
        </div>"""
        return HTMLResponse(result_html)
    except Exception as e:
        logger.error(f"Prediction failed for {city}: {e}")
        return HTMLResponse(f'<div class="text-red-400 p-4">Prediction failed: {str(e)}</div>')


@router.post("/trade", response_class=HTMLResponse)
async def trade(request: Request, city: str = Form(...)):
    try:
        pred = await fetch_one("SELECT * FROM predictions WHERE city=? ORDER BY created_at DESC LIMIT 1", (city,))
        if not pred:
            return HTMLResponse('<div class="text-amber-400 p-2">No prediction available. Run prediction first.</div>')
        from app.schemas.prediction import PredictionResult
        prediction = PredictionResult(**{k: pred[k] for k in
            ["city", "model_probability", "market_probability", "edge", "recommendation",
             "reasoning", "confidence", "weather_summary"]})
        state = await portfolio_agent.get_state()
        sizing = risk_agent.compute_kelly(prediction, state.balance)
        exposure = await portfolio_agent.get_open_exposure()
        sizing.position_size = risk_agent.check_portfolio_exposure(exposure, sizing.position_size, state.balance)
        trade_result = await trading_agent.execute_trade(prediction, sizing, pred["id"])
        if trade_result:
            return HTMLResponse(f"""
            <div class="text-emerald-400 p-3 bg-emerald-500/10 rounded-lg mt-2 text-sm">
                ✅ Trade executed: {trade_result.direction} {city} ${trade_result.size:.2f} @ {trade_result.entry_price:.4f}
            </div>""")
        return HTMLResponse('<div class="text-amber-400 p-2 text-sm">No trade — HOLD recommendation or zero sizing.</div>')
    except Exception as e:
        logger.error(f"Trade failed for {city}: {e}")
        return HTMLResponse(f'<div class="text-red-400 p-2">Trade error: {str(e)}</div>')


@router.post("/hedge", response_class=HTMLResponse)
async def hedge(request: Request, city: str = Form(...)):
    try:
        report = await research_agent.research(city)
        if "error" in report:
            return HTMLResponse(f'<div class="text-red-400 p-2">{report["error"]}</div>')
        prediction = await hermes_client.predict(report["weather"], report["market"])
        hedge_event = await trading_agent.check_and_hedge(prediction)
        if hedge_event:
            return HTMLResponse(f"""
            <div class="text-amber-400 p-3 bg-amber-500/10 rounded-lg text-sm">
                🔄 Hedge triggered: {hedge_event.action_taken}<br>
                Reason: {hedge_event.trigger_reason}<br>
                Edge: {hedge_event.pre_edge:+.4f} → {hedge_event.post_edge:+.4f}
            </div>""")
        return HTMLResponse('<div class="text-gray-400 p-2 text-sm">No hedge needed — edge still favorable.</div>')
    except Exception as e:
        logger.error(f"Hedge check failed for {city}: {e}")
        return HTMLResponse(f'<div class="text-red-400 p-2">Hedge error: {str(e)}</div>')


@router.post("/resolve/{trade_id}", response_class=HTMLResponse)
async def resolve(request: Request, trade_id: int):
    try:
        trade = await trading_agent.resolve_trade(trade_id)
        if trade:
            return HTMLResponse(f"""
            <div class="text-emerald-400 p-2 bg-emerald-500/10 rounded-lg text-xs mt-1">
                ✅ Resolved: {'Won' if trade.pnl > 0 else 'Lost'} ${abs(trade.pnl):.2f} (Exit: {trade.exit_price:.2f})
            </div>""")
        return HTMLResponse('<div class="text-amber-400 p-2 text-xs mt-1">Could not resolve trade.</div>')
    except Exception as e:
        logger.error(f"Resolution failed for trade {trade_id}: {e}")
        return HTMLResponse(f'<div class="text-red-400 p-2 text-xs mt-1">Error: {str(e)}</div>')


@router.post("/refresh", response_class=HTMLResponse)
async def refresh(request: Request):
    results = []
    for city_key in CityConfig.get_city_names():
        try:
            report = await research_agent.research(city_key)
            if "error" not in report:
                prediction = await hermes_client.predict(report["weather"], report["market"])
                hedge_event = await trading_agent.check_and_hedge(prediction)
                status = "hedged" if hedge_event else "updated"
                results.append(f"{city_key}: {status}")
            else:
                results.append(f"{city_key}: error")
        except Exception as e:
            results.append(f"{city_key}: failed ({str(e)[:50]})")
            logger.error(f"Refresh failed for {city_key}: {e}")
    return HTMLResponse(f"""
    <div class="text-emerald-400 p-3 bg-emerald-500/10 rounded-lg text-sm">
        ✅ Refresh complete<br>{'<br>'.join(results)}
    </div>""")


@router.get("/htmx/dashboard-stats", response_class=HTMLResponse)
async def htmx_dashboard_stats(request: Request):
    state = await portfolio_agent.get_state()
    return templates.TemplateResponse(request=request, name="partials/dashboard_stats.html", context={
        "request": request, "portfolio": state,
    })


@router.get("/htmx/trade-history", response_class=HTMLResponse)
async def htmx_trade_history(request: Request):
    trades = await fetch_all("SELECT * FROM trades ORDER BY created_at DESC LIMIT 20")
    return templates.TemplateResponse(request=request, name="partials/trade_history.html", context={
        "request": request, "trades": trades,
    })
