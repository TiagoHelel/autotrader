"""
AutoTrader Command Center - FastAPI Backend
REST + WebSocket API serving mock FOREX trading data.
News auto-refresh a cada 5 minutos via background task.
"""

import sys
import json
import math
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# JSON response com sanitizacao global de NaN/Inf
# ---------------------------------------------------------------------------
# Starlette serializa com allow_nan=False -> qualquer NaN/Inf derruba a request.
# Numpy/pandas geram NaN com frequencia (ex: mean de serie vazia, div-zero em
# metricas), entao convertemos recursivamente para None antes de serializar.
def _sanitize_json(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(_sanitize_json(content))

logger = logging.getLogger(__name__)

# Add project root to path for prediction API imports
# Use resolve() to handle uvicorn reload subprocess correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import init_db, get_conn
from ws_manager import ws_manager


# ---------------------------------------------------------------------------
# News background task
# ---------------------------------------------------------------------------
_news_task = None

async def _news_refresh_loop():
    """Background task: busca noticias a cada 5 minutos."""
    from src.llm.news_sentiment import LLMShutdown

    while True:
        try:
            await asyncio.to_thread(_fetch_and_process_news)
        except LLMShutdown:
            logger.info("News refresh interrompido por shutdown")
            return
        except Exception as e:
            logger.error(f"News refresh error: {e}")
        try:
            await asyncio.sleep(300)  # 5 minutos
        except asyncio.CancelledError:
            return


def _fetch_and_process_news():
    """Executa pipeline de noticias (sync, roda em thread)."""
    try:
        from src.data.news.investing import run_news_ingestion, load_news_raw
        from src.features.news_features import normalize_news
        from src.llm.news_sentiment import process_news_with_llm, save_llm_features

        logger.info("News refresh: fetching...")
        news_df = run_news_ingestion()
        if news_df.empty:
            logger.info("News refresh: no events found")
            return

        logger.info(f"News refresh: {len(news_df)} events fetched")

        # Process with LLM
        try:
            normalized = normalize_news(news_df)
            llm_df = process_news_with_llm(normalized)
            if not llm_df.empty:
                save_llm_features(llm_df)
                logger.info(f"News refresh: LLM processed {len(llm_df)} events")
        except Exception as e:
            logger.warning(f"News refresh: LLM failed (fallback active): {e}")

    except Exception as e:
        logger.error(f"News refresh pipeline error: {e}")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _news_task
    # Startup
    init_db()
    ws_manager.start()

    # Start news background refresh (fetch immediately + every 5min)
    _news_task = asyncio.create_task(_news_refresh_loop())
    logger.info("News background refresh started (every 5 min)")

    yield

    # Shutdown
    # Sinaliza o processamento LLM em batch para abortar antes da proxima noticia.
    # Sem isto, a task fica presa dentro de `asyncio.to_thread` (httpx sync) e
    # o cancel do asyncio nao interrompe a thread, travando o Ctrl+C por minutos.
    try:
        from src.llm.news_sentiment import shutdown_event as llm_shutdown_event
        llm_shutdown_event.set()
    except Exception:
        pass

    if _news_task:
        _news_task.cancel()
        try:
            await asyncio.wait_for(_news_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    await ws_manager.stop()


app = FastAPI(
    title="AutoTrader Command Center",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

# CORS - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount prediction API router
print(f"[DEBUG] PROJECT_ROOT={PROJECT_ROOT}, exists={PROJECT_ROOT.exists()}, src={(PROJECT_ROOT / 'src').exists()}")
try:
    from src.api.predictions import router as predictions_router
    app.include_router(predictions_router)
    print(f"Prediction API loaded: {len(predictions_router.routes)} routes")
except Exception as e:
    import traceback
    print(f"WARNING: Could not load prediction API: {e}")
    traceback.print_exc()

try:
    from src.api.news_regime import router as news_regime_router
    app.include_router(news_regime_router)
    print(f"News/Regime API loaded: {len(news_regime_router.routes)} routes")
except Exception as e:
    import traceback
    print(f"WARNING: Could not load news/regime API: {e}")
    traceback.print_exc()

try:
    from src.api.backtest_experiments import router as bt_exp_router
    app.include_router(bt_exp_router)
    print(f"Backtest/Experiments API loaded: {len(bt_exp_router.routes)} routes")
except Exception as e:
    import traceback
    print(f"WARNING: Could not load backtest/experiments API: {e}")
    traceback.print_exc()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/account")
def get_account():
    """Account KPIs: balance, equity, PnL, drawdown, win-rate."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM account_state ORDER BY id DESC LIMIT 1").fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


@app.get("/api/positions")
def get_positions():
    """Currently open positions."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM positions ORDER BY open_time DESC").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/positions/history")
def get_trade_history(limit: int = Query(default=50, ge=1, le=500)):
    """Closed trade history."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM trade_history ORDER BY close_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/predictions")
def get_predictions():
    """All recent predictions."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM predictions ORDER BY timestamp DESC").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/predictions/latest")
def get_latest_predictions():
    """Latest prediction per symbol."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT p.*
            FROM predictions p
            INNER JOIN (
                SELECT symbol, MAX(timestamp) as max_ts
                FROM predictions
                GROUP BY symbol
            ) latest ON p.symbol = latest.symbol AND p.timestamp = latest.max_ts
            ORDER BY p.timestamp DESC
        """).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/news")
def get_news(limit: int = Query(default=30, ge=1, le=200)):
    """News feed with sentiment data."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM news ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/model/metrics")
def get_model_metrics():
    """ML model performance metrics."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM model_metrics ORDER BY model_name").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/model/features")
def get_feature_importance():
    """Feature importance per model."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM feature_importance ORDER BY model_name, importance DESC"
        ).fetchall()
        # Group by model
        result: dict[str, list[dict]] = {}
        for row in rows:
            d = dict(row)
            model = d.pop("model_name")
            result.setdefault(model, []).append(d)
        return result
    finally:
        conn.close()


@app.get("/api/equity/history")
def get_equity_history():
    """30-day equity curve for charting."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT equity, timestamp FROM equity_history ORDER BY timestamp ASC"
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/logs")
def get_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    level: str = Query(default="ALL"),
):
    """System logs, filterable by level."""
    conn = get_conn()
    try:
        if level.upper() == "ALL":
            rows = conn.execute(
                "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM logs WHERE level = ? ORDER BY timestamp DESC LIMIT ?",
                (level.upper(), limit),
            ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


@app.get("/api/bot/status")
def get_bot_status():
    """Bot operational status."""
    conn = get_conn()
    try:
        pos_count = conn.execute("SELECT COUNT(*) as cnt FROM positions").fetchone()["cnt"]
        symbols = conn.execute("SELECT DISTINCT symbol FROM positions").fetchall()
        active_symbols = [r["symbol"] for r in symbols]
    finally:
        conn.close()

    return {
        "status": "running",
        "current_symbols": active_symbols,
        "open_positions": pos_count,
        "timeframe": "M5",
        "uptime_seconds": 48723,
        "uptime_display": "13h 32m 03s",
        "started_at": (datetime.utcnow() - timedelta(seconds=48723)).isoformat(),
        "mode": "live",
        "mt5_connected": True,
        "last_heartbeat": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial state on connect
        conn = get_conn()
        try:
            account = conn.execute("SELECT * FROM account_state ORDER BY id DESC LIMIT 1").fetchone()
            positions = conn.execute("SELECT * FROM positions ORDER BY open_time DESC").fetchall()
            initial = {
                "type": "init",
                "data": {
                    "account": dict(account) if account else {},
                    "positions": [dict(r) for r in positions],
                },
            }
        finally:
            conn.close()

        await ws.send_text(json.dumps(initial, default=str))

        # Keep connection alive, listen for client messages
        while True:
            data = await ws.receive_text()
            # Echo/ack any client messages
            await ws.send_text(json.dumps({"type": "ack", "data": data}))
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
