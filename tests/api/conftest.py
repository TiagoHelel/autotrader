"""
Fixtures da su\u00edte de API.

Monta uma app FastAPI leve contendo apenas os routers, sem o lifespan
do backend principal (que dispara news refresh + websocket manager).
Isso mant\u00e9m os testes < 5s e determin\u00edsticos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import math
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sanitize_json(obj):
    """Mesma sanitiza\u00e7\u00e3o usada em produ\u00e7\u00e3o (main.py) \u2014 NaN/Inf -> None."""
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


def _build_test_app() -> FastAPI:
    """FastAPI minimalista com os mesmos routers usados em produ\u00e7\u00e3o."""
    app = FastAPI(
        title="AutoTrader Test App",
        default_response_class=SafeJSONResponse,
    )

    from src.api.predictions import router as predictions_router
    from src.api.news_regime import router as news_regime_router
    from src.api.backtest_experiments import router as bt_exp_router

    app.include_router(predictions_router)
    app.include_router(news_regime_router)
    app.include_router(bt_exp_router)
    return app


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return _build_test_app()


@pytest.fixture(scope="session")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def has_predictions() -> bool:
    from config.settings import settings
    return any(settings.predictions_dir.glob("*.parquet"))


@pytest.fixture(scope="session")
def has_features() -> bool:
    from config.settings import settings
    fdir = getattr(settings, "features_dir", ROOT / "data" / "features")
    return any(Path(fdir).glob("*.parquet"))
