"""
API HTTP fina para expor o MetaTrader 5 via pull.

Roda na maquina Windows que tem o terminal MT5 instalado. Outras maquinas
(Linux com o sistema principal) consomem candles, tick e info de conta
via HTTP em vez de importar `MetaTrader5` direto.

Endpoints:
    GET  /health
    GET  /account
    GET  /terminal
    GET  /symbols?group=*USD*
    GET  /symbols/{symbol}
    GET  /symbols/{symbol}/tick
    GET  /candles/{symbol}?tf=M1&count=1000
    GET  /candles/{symbol}?tf=M1&date_from=2026-04-01T00:00:00&date_to=...

Auth opcional via env `MT5_API_TOKEN`. Se setado, requer header
`Authorization: Bearer <token>` em todas as rotas (exceto /health).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# Garante que o root do repo entra no sys.path quando rodado direto.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from src.mt5.connection import MT5Connection, MT5ConnectionError  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# A lib MetaTrader5 nao eh thread-safe: serializa acesso na app inteira.
_MT5_LOCK = threading.Lock()
_API_TOKEN = os.getenv("MT5_API_TOKEN", "").strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Conecta ao MT5 no startup e desconecta no shutdown."""
    conn = MT5Connection()
    try:
        conn.connect()
    except MT5ConnectionError:
        logger.exception("Falha ao conectar no MT5 durante startup.")
        raise
    app.state.mt5 = conn
    logger.info("MT5 API pronta. Token auth: %s", "ON" if _API_TOKEN else "OFF")
    try:
        yield
    finally:
        conn.disconnect()
        logger.info("MT5 API desligada.")


app = FastAPI(
    title="AutoTrader MT5 Bridge",
    description="Servidor HTTP fino que expoe MetaTrader 5 via pull.",
    version="0.1.0",
    lifespan=lifespan,
)


def require_token(request: Request) -> None:
    """Valida bearer token se MT5_API_TOKEN estiver configurado."""
    if not _API_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {_API_TOKEN}"
    if auth != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou ausente.",
        )


def get_conn(request: Request) -> MT5Connection:
    return request.app.state.mt5


@app.exception_handler(MT5ConnectionError)
async def mt5_error_handler(request: Request, exc: MT5ConnectionError):  # noqa: ARG001
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


@app.get("/health")
def health(request: Request) -> dict:
    """Sem auth. Reporta se a conexao com o MT5 esta viva."""
    conn: Optional[MT5Connection] = getattr(request.app.state, "mt5", None)
    return {
        "status": "ok" if conn and conn.is_connected else "down",
        "connected": bool(conn and conn.is_connected),
    }


@app.get("/account", dependencies=[Depends(require_token)])
def account(conn: MT5Connection = Depends(get_conn)) -> dict:
    with _MT5_LOCK:
        return conn.account_info()


@app.get("/terminal", dependencies=[Depends(require_token)])
def terminal(conn: MT5Connection = Depends(get_conn)) -> dict:
    with _MT5_LOCK:
        return conn.terminal_info()


@app.get("/symbols", dependencies=[Depends(require_token)])
def list_symbols(
    group: str = Query("*", description="Filtro estilo MT5, ex: *USD*"),
    conn: MT5Connection = Depends(get_conn),
) -> dict:
    with _MT5_LOCK:
        symbols = conn.get_available_symbols(group=group)
    return {"group": group, "count": len(symbols), "symbols": symbols}


@app.get("/symbols/{symbol}", dependencies=[Depends(require_token)])
def symbol_info(symbol: str, conn: MT5Connection = Depends(get_conn)) -> dict:
    with _MT5_LOCK:
        return conn.symbol_info(symbol)


@app.get("/symbols/{symbol}/tick", dependencies=[Depends(require_token)])
def symbol_tick(symbol: str, conn: MT5Connection = Depends(get_conn)) -> dict:
    with _MT5_LOCK:
        tick = conn.get_tick(symbol)
    # datetime nao eh JSON-serializavel direto.
    tick["time"] = tick["time"].isoformat()
    return tick


@app.get("/candles/{symbol}", dependencies=[Depends(require_token)])
def candles(
    symbol: str,
    tf: str = Query("M1", description="M1, M5, M15, M30, H1, H4, D1, W1, MN1"),
    count: int = Query(1000, ge=1, le=100_000),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    conn: MT5Connection = Depends(get_conn),
) -> dict:
    """
    Retorna candles em formato JSON (lista de dicts).

    - `tf`: string de timeframe (case-insensitive).
    - Sem `date_from`/`date_to`: ultimos `count` candles.
    - Com `date_from` apenas: `count` candles a partir da data.
    - Com `date_from` + `date_to`: range completo (ignora `count`).
    """
    with _MT5_LOCK:
        df = conn.get_candles(
            symbol=symbol,
            timeframe=tf,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    if df.empty:
        return {"symbol": symbol, "tf": tf, "count": 0, "candles": []}

    # Serializacao: time -> ISO string, demais colunas viram float/int nativos.
    df = df.copy()
    df["time"] = df["time"].dt.tz_localize(None).astype(str)
    records = df.to_dict(orient="records")
    return {
        "symbol": symbol,
        "tf": tf,
        "count": len(records),
        "candles": records,
    }


def main() -> None:
    """Entry point para `python -m mt5_api.main`."""
    import uvicorn

    host = os.getenv("MT5_API_HOST", "0.0.0.0")
    port = int(os.getenv("MT5_API_PORT", "8002"))
    uvicorn.run(
        "mt5_api.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
