"""
FastAPI router para endpoints de noticias, regime de mercado e LLM.
"""

import logging
import threading
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Query

from src.data.news.investing import load_news_raw, run_news_ingestion
from src.features.news_features import normalize_news, build_news_features
from src.features.regime import get_current_regime
from src.features.session import get_current_session_info, SESSION_WEIGHTS
from src.features.engineering import load_features
from src.llm.news_sentiment import load_llm_features, process_news_with_llm, save_llm_features
from src.mt5.symbols import get_symbol_currencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["news-regime"])
_news_refresh_status = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "count": 0,
    "llm_count": 0,
    "error": None,
}
_news_refresh_lock = threading.Lock()


def _run_news_refresh_job() -> None:
    """Executa refresh completo em background."""
    with _news_refresh_lock:
        _news_refresh_status.update({
            "running": True,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "count": 0,
            "llm_count": 0,
            "error": None,
        })

    try:
        news_df = run_news_ingestion(force=True)
        if news_df.empty:
            _news_refresh_status.update({
                "running": False,
                "finished_at": datetime.utcnow().isoformat(),
                "count": 0,
                "llm_count": 0,
                "error": None,
            })
            return

        normalized = normalize_news(news_df)
        llm_count = 0

        try:
            llm_df = process_news_with_llm(normalized)
            if not llm_df.empty:
                save_llm_features(llm_df)
                llm_count = len(llm_df)
        except Exception as e:
            logger.warning(f"LLM processing failed: {e}")

        _news_refresh_status.update({
            "running": False,
            "finished_at": datetime.utcnow().isoformat(),
            "count": len(news_df),
            "llm_count": llm_count,
            "error": None,
        })
    except Exception as e:
        logger.exception("News refresh job failed")
        _news_refresh_status.update({
            "running": False,
            "finished_at": datetime.utcnow().isoformat(),
            "error": str(e),
        })


# ---------------------------------------------------------------------------
# NEWS endpoints
# ---------------------------------------------------------------------------

@router.post("/api/news/refresh")
def refresh_news():
    """Dispara refresh manual em background."""
    if _news_refresh_status["running"]:
        return {
            "status": "running",
            "message": "News refresh already in progress",
            **_news_refresh_status,
        }

    thread = threading.Thread(target=_run_news_refresh_job, daemon=True)
    thread.start()
    return {
        "status": "accepted",
        "message": "News refresh started in background",
        **_news_refresh_status,
    }


@router.get("/api/news/refresh/status")
def get_news_refresh_status():
    """Status do refresh manual/automatico de noticias."""
    return {
        "status": "running" if _news_refresh_status["running"] else "idle",
        **_news_refresh_status,
    }


@router.get("/api/news/latest")
def get_news_latest(limit: int = Query(default=50, ge=1, le=500)):
    """Ultimas noticias do economic calendar."""
    df = load_news_raw()
    if df.empty:
        return {"events": [], "count": 0}

    df = normalize_news(df)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp", ascending=False).head(limit)
        df["timestamp"] = df["timestamp"].astype(str)

    # Converter signal objects para string se necessario
    for col in df.columns:
        df[col] = df[col].astype(str).replace("nan", "")

    return {
        "events": df.to_dict(orient="records"),
        "count": len(df),
    }


@router.get("/api/news/features")
def get_news_features(symbol: str = Query(default="EURUSD")):
    """Features de noticias computadas para um simbolo."""
    df = load_news_raw()
    if df.empty:
        return {"features": {}, "symbol": symbol}

    normalized = normalize_news(df)
    llm_df = load_llm_features()

    features = build_news_features(
        symbol=symbol,
        current_time=datetime.utcnow(),
        news_df=normalized,
        llm_df=llm_df if not llm_df.empty else None,
    )

    return {"features": features, "symbol": symbol}


@router.get("/api/news/llm")
def get_news_llm(limit: int = Query(default=50, ge=1, le=500)):
    """Features LLM das noticias."""
    df = load_llm_features()
    if df.empty:
        return {"llm_features": [], "count": 0}

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp", ascending=False).head(limit)
        df["timestamp"] = df["timestamp"].astype(str)

    return {
        "llm_features": df.to_dict(orient="records"),
        "count": len(df),
    }


@router.get("/api/news/by-symbol")
def get_news_by_symbol(
    symbol: str = Query(default="EURUSD"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Noticias filtradas pelas moedas de um par forex."""
    df = load_news_raw()
    if df.empty:
        return {"events": [], "symbol": symbol}

    normalized = normalize_news(df)
    base, quote = get_symbol_currencies(symbol)

    # Filtrar por moeda base ou quote
    mask = normalized["currency"].isin([base, quote])
    filtered = normalized[mask]

    if "timestamp" in filtered.columns:
        filtered["timestamp"] = pd.to_datetime(filtered["timestamp"], errors="coerce")
        filtered = filtered.sort_values("timestamp", ascending=False).head(limit)
        filtered["timestamp"] = filtered["timestamp"].astype(str)

    for col in filtered.columns:
        filtered[col] = filtered[col].astype(str).replace("nan", "")

    return {
        "events": filtered.to_dict(orient="records"),
        "symbol": symbol,
        "base_currency": base,
        "quote_currency": quote,
        "count": len(filtered),
    }


# ---------------------------------------------------------------------------
# REGIME endpoints
# ---------------------------------------------------------------------------

@router.get("/api/regime/current")
def get_regime_current(symbol: str = Query(default="EURUSD")):
    """Regime de mercado atual para um simbolo."""
    featured_df = load_features(symbol)
    if featured_df.empty:
        return {
            "symbol": symbol,
            "regime": {
                "trend": 0,
                "trend_label": "unknown",
                "volatility_regime": 1,
                "volatility_label": "medium",
                "momentum": 0.0,
                "range_flag": 0,
                "range_label": "unknown",
            },
        }

    regime = get_current_regime(featured_df)
    return {"symbol": symbol, "regime": regime}


# ---------------------------------------------------------------------------
# SESSION endpoints
# ---------------------------------------------------------------------------

@router.get("/api/session/current")
def get_session_current(symbol: str = Query(default="EURUSD")):
    """
    Sessao de mercado atual para um simbolo.
    Retorna sessoes ativas, session_score, regime atual e weights.
    """
    session_info = get_current_session_info(symbol)

    # Adicionar regime atual se disponivel
    featured_df = load_features(symbol)
    regime = {}
    if not featured_df.empty:
        regime = get_current_regime(featured_df)

    session_info["regime"] = regime
    return session_info


@router.get("/api/session/weights")
def get_session_weights():
    """Retorna os pesos de sessao para todos os ativos."""
    return {"weights": SESSION_WEIGHTS}


# ---------------------------------------------------------------------------
# NEWS ANALYTICS (agregado)
# ---------------------------------------------------------------------------

@router.get("/api/news/analytics")
def get_news_analytics():
    """Analise completa de noticias: por moeda, impacto, sentimento."""
    df = load_news_raw()
    if df.empty:
        return {"analytics": {}}

    normalized = normalize_news(df)
    llm_df = load_llm_features()

    # Stats por moeda
    currency_stats = {}
    if "currency" in normalized.columns:
        for currency in normalized["currency"].unique():
            if not currency:
                continue
            curr_df = normalized[normalized["currency"] == currency]
            stats = {
                "total_events": len(curr_df),
                "avg_impact": float(curr_df["impact_num"].mean()) if "impact_num" in curr_df.columns else 0,
                "sentiment_basic_avg": float(curr_df["sentiment_basic"].mean()) if "sentiment_basic" in curr_df.columns else 0,
                "high_impact_count": int((curr_df["impact_num"] >= 3).sum()) if "impact_num" in curr_df.columns else 0,
            }

            # Adicionar LLM sentiment se disponivel
            merge_cols = [col for col in ["timestamp", "name", "country"] if col in curr_df.columns and col in llm_df.columns]
            if not llm_df.empty and merge_cols:
                llm_fields = [col for col in ["sentiment_score", "used_fallback"] if col in llm_df.columns]
                merged = curr_df.merge(
                    llm_df[merge_cols + llm_fields],
                    on=merge_cols,
                    how="left",
                )
                if "sentiment_score" in merged.columns:
                    stats["sentiment_llm_avg"] = float(merged["sentiment_score"].mean())
                if "used_fallback" in merged.columns:
                    stats["llm_fallback_rate"] = float(merged["used_fallback"].fillna(False).mean())

            currency_stats[currency] = stats

    # Stats por impacto
    impact_dist = {}
    if "impact_num" in normalized.columns:
        for impact in [1, 2, 3]:
            count = int((normalized["impact_num"] == impact).sum())
            impact_dist[str(impact)] = count

    # Comparacao basic vs LLM
    comparison = []
    merge_cols = [col for col in ["timestamp", "name", "country"] if col in normalized.columns and col in llm_df.columns]
    if not llm_df.empty and merge_cols and "sentiment_basic" in normalized.columns:
        llm_fields = [col for col in ["sentiment_score", "confidence", "used_fallback", "reasoning_short"] if col in llm_df.columns]
        merged = normalized.merge(
            llm_df[merge_cols + llm_fields],
            on=merge_cols,
            how="inner",
        )
        if not merged.empty:
            for _, row in merged.head(20).iterrows():
                comparison.append({
                    "name": str(row.get("name", "")),
                    "country": str(row.get("country", "")),
                    "basic": float(row.get("sentiment_basic", 0)),
                    "llm": float(row.get("sentiment_score", 0)),
                    "confidence": float(row.get("confidence", 0)),
                    "used_fallback": bool(row.get("used_fallback", False)),
                    "reasoning_short": str(row.get("reasoning_short", "")),
                })

    return {
        "analytics": {
            "by_currency": currency_stats,
            "by_impact": impact_dist,
            "basic_vs_llm": comparison,
            "total_events": len(normalized),
        }
    }
