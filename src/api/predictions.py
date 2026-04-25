"""
FastAPI router para endpoints de previsao.
GET /symbols, /metrics, /predictions, /models/performance
"""

import logging
import math
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Query

from config.settings import settings
from src.evaluation.evaluator import get_model_performance, get_performance_over_time, load_metrics
from src.evaluation.feature_importance import load_feature_importance
from src.evaluation.overfitting import OVERFIT_THRESHOLD, get_latest_validation
from src.evaluation.tracker import get_experiments, get_experiment_summary


def _finite_or(value, default=0.0):
    """Converte NaN/Inf em `default` para evitar erro de JSON (`allow_nan=False`)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return v

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predict", tags=["predictions"])
_radar_cache = {
    "until": None,
    "payload": None,
}
RADAR_CACHE_TTL_SECONDS = 60


def _sanitize_prediction_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove previsoes obviamente invalidas para o frontend/API."""
    if df.empty:
        return df

    pred_cols = [c for c in ["pred_t1", "pred_t2", "pred_t3", "current_price"] if c in df.columns]
    for col in pred_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "current_price" not in df.columns:
        return df

    # Predicoes de preco precisam ser positivas e minimamente plausiveis
    for col in [c for c in ["pred_t1", "pred_t2", "pred_t3"] if c in df.columns]:
        invalid = (
            df[col].isna()
            | (df[col] <= 0)
            | (df["current_price"] > 0) & (df[col] < df["current_price"] * 0.2)
            | (df["current_price"] > 0) & (df[col] > df["current_price"] * 5.0)
        )
        df.loc[invalid, col] = pd.NA

    return df


@router.get("/symbols")
def get_symbols():
    """Lista simbolos ativos com status (inclui desejados sem dados)."""
    from src.mt5.symbols import DESIRED_SYMBOLS

    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Simbolos com dados coletados
    seen = set()
    symbols = []
    for f in raw_dir.glob("*.parquet"):
        symbol = f.stem
        seen.add(symbol)
        df = pd.read_parquet(f)
        symbols.append({
            "symbol": symbol,
            "candles": len(df),
            "last_update": df["time"].max().isoformat() if not df.empty else None,
            "first_candle": df["time"].min().isoformat() if not df.empty else None,
            "status": "active",
        })

    # Simbolos desejados sem dados ainda (ex: XAUUSD)
    for symbol in DESIRED_SYMBOLS:
        if symbol not in seen:
            symbols.append({
                "symbol": symbol,
                "candles": 0,
                "last_update": None,
                "first_candle": None,
                "status": "pending",
            })

    # Ordenar: DESIRED_SYMBOLS primeiro, na ordem original
    order = {s: i for i, s in enumerate(DESIRED_SYMBOLS)}
    symbols.sort(key=lambda x: order.get(x["symbol"], 999))

    return {"symbols": symbols, "count": len(symbols)}


@router.get("/metrics")
def get_metrics(symbol: str = Query(default=None)):
    """Metricas de avaliacao agregadas."""
    perf = get_model_performance(symbol)
    if perf.empty:
        return {"metrics": [], "global": {}}

    global_stats = {
        "total_predictions": int(perf["total_predictions"].sum()),
        "total_correct": int(perf["correct_predictions"].sum()),
        "global_accuracy": float(
            perf["correct_predictions"].sum() / perf["total_predictions"].sum() * 100
        ) if perf["total_predictions"].sum() > 0 else 0,
        "global_mae": float(perf["mae"].mean()),
        "global_mape": float(perf["mape"].mean()),
    }

    return {
        "metrics": perf.to_dict(orient="records"),
        "global": global_stats,
    }


@router.get("/predictions")
def get_predictions(
    symbol: str = Query(default=None),
    model: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Previsoes recentes."""
    pred_dir = settings.predictions_dir
    if not pred_dir.exists():
        return {"predictions": []}

    dfs = []
    if symbol:
        f = pred_dir / f"{symbol}.parquet"
        if f.exists():
            dfs.append(pd.read_parquet(f))
    else:
        for f in pred_dir.glob("*.parquet"):
            dfs.append(pd.read_parquet(f))

    if not dfs:
        return {"predictions": []}

    combined = pd.concat(dfs, ignore_index=True)
    combined = _sanitize_prediction_rows(combined)
    if model:
        combined = combined[combined["model"] == model]

    combined = combined.sort_values("timestamp", ascending=False).head(limit)
    return {"predictions": combined.to_dict(orient="records")}


@router.get("/predictions/latest")
def get_latest_prediction(symbol: str = Query(...)):
    """
    Ultima previsao por simbolo, com ensemble (media dos modelos) para t+1, t+2, t+3.

    Resposta:
        {
            "symbol": "EURUSD",
            "timestamp": "2026-04-10T10:55:09",
            "current_price": 1.17133,
            "ensemble": {"pred_t1": ..., "pred_t2": ..., "pred_t3": ...},
            "models": [{"model": "xgboost", "pred_t1": ..., ...}, ...],
            "n_models": 5,
            "confidence": 0.83  # 1 - dispersao normalizada entre modelos
        }

    Retorna 404 se o simbolo nao estiver na whitelist (DESIRED_SYMBOLS + FALLBACK).
    """
    from fastapi import HTTPException
    from src.mt5.symbols import DESIRED_SYMBOLS, FALLBACK_SYMBOLS

    allowed = set(DESIRED_SYMBOLS) | set(FALLBACK_SYMBOLS)
    if symbol not in allowed:
        raise HTTPException(status_code=404, detail=f"symbol '{symbol}' nao reconhecido")

    pred_dir = settings.predictions_dir
    f = pred_dir / f"{symbol}.parquet"
    if not f.exists():
        return {"symbol": symbol, "ensemble": None, "models": [], "n_models": 0}

    df = pd.read_parquet(f)
    df = _sanitize_prediction_rows(df)
    if df.empty:
        return {"symbol": symbol, "ensemble": None, "models": [], "n_models": 0}

    # Pega o timestamp mais recente
    df = df.sort_values("timestamp", ascending=False)
    latest_ts = df["timestamp"].iloc[0]
    latest = df[df["timestamp"] == latest_ts].copy()

    # Ensemble = media dos modelos para cada horizonte
    ensemble = {
        "pred_t1": float(latest["pred_t1"].mean(skipna=True)) if "pred_t1" in latest else None,
        "pred_t2": float(latest["pred_t2"].mean(skipna=True)) if "pred_t2" in latest else None,
        "pred_t3": float(latest["pred_t3"].mean(skipna=True)) if "pred_t3" in latest else None,
    }

    # Confianca = 1 - (desvio padrao normalizado pelo current_price)
    current_price = float(latest["current_price"].iloc[0]) if "current_price" in latest else 0.0
    confidence = None
    if current_price > 0 and len(latest) > 1:
        stds = []
        for col in ["pred_t1", "pred_t2", "pred_t3"]:
            if col in latest:
                s = latest[col].std(skipna=True)
                if pd.notna(s):
                    stds.append(s / current_price)
        if stds:
            avg_disp = sum(stds) / len(stds)
            # Normaliza: dispersao tipica de 0.001 (~10 pips) -> conf ~0.5
            confidence = max(0.0, min(1.0, 1.0 - (avg_disp * 500)))

    models = latest[[c for c in ["model", "pred_t1", "pred_t2", "pred_t3"] if c in latest.columns]]
    models = models.where(pd.notna(models), None)

    return {
        "symbol": symbol,
        "timestamp": str(latest_ts),
        "current_price": current_price,
        "ensemble": ensemble,
        "models": models.to_dict(orient="records"),
        "n_models": int(len(latest)),
        "confidence": confidence,
    }


@router.get("/signals/radar")
def get_radar_signals():
    """
    Sinais ensemble para TODOS os simbolos ativos — usado pelo Signal Radar.

    Para cada simbolo com previsoes, calcula:
      1. Ensemble (media dos modelos) para pred_t1/t2/t3
      2. Sinal (BUY/SELL/HOLD) via generate_signal() sobre o ensemble
      3. Confianca consolidada

    Retorna lista com todos os DESIRED_SYMBOLS (11),
    mesmo os sem dados (signal=HOLD, confidence=0).
    """
    from src.decision.signal import generate_signal
    from src.mt5.symbols import DESIRED_SYMBOLS

    cache_until = _radar_cache.get("until")
    cache_payload = _radar_cache.get("payload")
    if cache_until and cache_payload and datetime.utcnow() < cache_until:
        return cache_payload

    pred_dir = settings.predictions_dir
    results = []

    for symbol in DESIRED_SYMBOLS:
        f = pred_dir / f"{symbol}.parquet"
        if not f.exists():
            results.append({
                "symbol": symbol,
                "signal": "HOLD",
                "confidence": 0.0,
                "expected_return": 0.0,
                "source": "no_data",
            })
            continue

        try:
            df = pd.read_parquet(f)
            df = _sanitize_prediction_rows(df)
            if df.empty:
                results.append({
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "expected_return": 0.0,
                    "source": "no_data",
                })
                continue

            df = df.sort_values("timestamp", ascending=False)
            latest_ts = df["timestamp"].iloc[0]
            latest = df[df["timestamp"] == latest_ts].copy()

            # Ensemble = media dos modelos (pode ser NaN se todos os modelos forem invalidos apos sanitize)
            ensemble_preds = {
                "pred_t1": latest["pred_t1"].mean(skipna=True) if "pred_t1" in latest else float("nan"),
                "pred_t2": latest["pred_t2"].mean(skipna=True) if "pred_t2" in latest else float("nan"),
                "pred_t3": latest["pred_t3"].mean(skipna=True) if "pred_t3" in latest else float("nan"),
            }
            current_price = float(latest["current_price"].iloc[0]) if "current_price" in latest else 0.0

            if current_price <= 0 or not math.isfinite(current_price):
                results.append({
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "expected_return": 0.0,
                    "source": "invalid_price",
                })
                continue

            # Se todas as previsoes do ensemble sao NaN/Inf, nao ha como gerar sinal
            if not any(math.isfinite(float(v)) for v in ensemble_preds.values() if pd.notna(v)):
                results.append({
                    "symbol": symbol,
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "expected_return": 0.0,
                    "source": "no_valid_predictions",
                })
                continue

            # Substitui NaN por current_price (neutro → ret=0) antes de passar ao generate_signal
            ensemble_preds = {k: _finite_or(v, current_price) for k, v in ensemble_preds.items()}

            sig = generate_signal(ensemble_preds, current_price)
            results.append({
                "symbol": symbol,
                "signal": sig["signal"],
                "confidence": _finite_or(sig["confidence"], 0.0),
                "expected_return": _finite_or(sig["expected_return"], 0.0),
                "source": "ensemble",
                "n_models": int(len(latest)),
                "current_price": _finite_or(current_price, 0.0),
                "timestamp": str(latest_ts),
            })
        except Exception as e:
            logger.warning(f"Radar: erro ao processar {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "signal": "HOLD",
                "confidence": 0.0,
                "expected_return": 0.0,
                "source": "error",
            })

    buy_count = sum(1 for r in results if r["signal"] == "BUY")
    sell_count = sum(1 for r in results if r["signal"] == "SELL")
    hold_count = sum(1 for r in results if r["signal"] == "HOLD")

    payload = {
        "signals": results,
        "total": len(results),
        "breakdown": {"BUY": buy_count, "SELL": sell_count, "HOLD": hold_count},
    }
    _radar_cache["payload"] = payload
    _radar_cache["until"] = datetime.utcnow() + timedelta(seconds=RADAR_CACHE_TTL_SECONDS)
    return payload


@router.get("/predictions/detail")
def get_predictions_with_actuals(
    symbol: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Previsoes com valores reais (para tabela do dashboard)."""
    metrics = load_metrics(symbol)
    if metrics.empty:
        return {"data": []}

    metrics = metrics.sort_values("timestamp", ascending=False).head(limit)
    return {"data": metrics.to_dict(orient="records")}


@router.get("/models/performance")
def get_models_performance():
    """Ranking de modelos por performance."""
    perf = get_model_performance()
    if perf.empty:
        return {"ranking": []}

    ranking = perf.to_dict(orient="records")
    for i, r in enumerate(ranking):
        r["rank"] = i + 1

    return {"ranking": ranking}


@router.get("/models/performance/over-time")
def get_models_performance_over_time(
    symbol: str = Query(default=None),
    model: str = Query(default=None),
):
    """Performance dos modelos ao longo do tempo."""
    perf = get_performance_over_time(symbol, model)
    if perf.empty:
        return {"data": []}

    perf["timestamp"] = perf["timestamp"].astype(str)
    return {"data": perf.to_dict(orient="records")}


@router.get("/models/info")
def get_models_info():
    """Informacoes sobre modelos disponiveis."""
    from src.models.registry import create_all_models
    models = create_all_models()
    return {
        "models": [
            {
                "name": m.name,
                "params": m.params,
                "features_used": m.features_used,
            }
            for m in models
        ]
    }


@router.get("/models/validation")
def get_models_validation(symbol: str = Query(default=None)):
    """
    Resultados de validacao CPCV por modelo.

    Retorna:
    - cpcv_score: media da accuracy across folds
    - std: desvio padrao (estabilidade)
    - overfit_gap: diferenca train vs val (overfitting indicator)
    - overfit_warning: True se gap > threshold
    """
    results = get_latest_validation(symbol)

    for r in results:
        r["overfit_warning"] = r.get("overfit_gap", 0) > OVERFIT_THRESHOLD
        # Cleanup
        r.pop("fold_scores", None)

    return {
        "validation": results,
        "overfit_threshold": OVERFIT_THRESHOLD,
    }


@router.get("/models/feature-importance")
def get_feature_importance_endpoint(
    symbol: str = Query(default=None),
    model: str = Query(default=None),
):
    """Feature importance por modelo (XGBoost gain, RF impurity)."""
    df = load_feature_importance(symbol, model)
    if df.empty:
        return {"importance": []}

    # Agregar por feature (media across horizons)
    agg = df.groupby(["model", "feature"]).agg(
        importance=("importance", "mean"),
    ).reset_index().sort_values("importance", ascending=False)

    return {"importance": agg.to_dict(orient="records")}


@router.get("/experiments")
def get_experiments_list(
    model: str = Query(default=None),
    symbol: str = Query(default=None),
):
    """Historico de experimentos."""
    exps = get_experiments(model, symbol)
    if exps.empty:
        return {"experiments": []}
    return {"experiments": exps.to_dict(orient="records")}


@router.get("/experiments/summary")
def get_experiments_summary_endpoint():
    """Resumo de todos os modelos testados."""
    summary = get_experiment_summary()
    if summary.empty:
        return {"summary": []}
    return {"summary": summary.to_dict(orient="records")}


@router.get("/candles")
def get_candles(
    symbol: str = Query(...),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Candles raw para graficos."""
    raw_dir = settings.raw_dir
    filepath = raw_dir / f"{symbol}.parquet"
    if not filepath.exists():
        return {"candles": []}

    df = pd.read_parquet(filepath)
    df = df.sort_values("time", ascending=False).head(limit)
    df = df.sort_values("time")
    df["time"] = df["time"].astype(str)
    return {"candles": df.to_dict(orient="records")}


@router.get("/system/status")
def get_system_status():
    """Status do sistema de previsao."""
    raw_dir = settings.raw_dir
    pred_dir = settings.predictions_dir

    n_symbols = len(list(raw_dir.glob("*.parquet"))) if raw_dir.exists() else 0
    n_predictions = 0
    last_update = None

    if pred_dir.exists():
        for f in pred_dir.glob("*.parquet"):
            df = pd.read_parquet(f)
            n_predictions += len(df)
            if not df.empty:
                ts = pd.Timestamp(df["timestamp"].max())
                if last_update is None or ts > last_update:
                    last_update = ts

    return {
        "status": "running" if n_symbols > 0 else "idle",
        "active_symbols": n_symbols,
        "total_predictions": n_predictions,
        "last_update": last_update.isoformat() if last_update else None,
        "timeframe": settings.timeframe,
    }


@router.get("/logs/recent")
def get_recent_logs(limit: int = Query(default=50, ge=1, le=500)):
    """Logs recentes do sistema."""
    import csv

    logs = []

    # Predictions log
    pred_log = settings.logs_dir / "predictions.csv"
    if pred_log.exists():
        with open(pred_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "prediction"
                logs.append(row)

    # Decisions log
    dec_log = settings.logs_dir / "decisions.csv"
    if dec_log.exists():
        with open(dec_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "decision"
                logs.append(row)

    # System log
    sys_log = settings.logs_dir / "system.csv"
    if sys_log.exists():
        with open(sys_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "system"
                logs.append(row)

    # Signals log
    sig_log = settings.logs_dir / "signals.csv"
    if sig_log.exists():
        with open(sig_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "signal"
                logs.append(row)

    # Session metrics log
    sess_log = settings.logs_dir / "session_metrics.csv"
    if sess_log.exists():
        with open(sess_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "session"
                logs.append(row)

    # Backtest trades log
    bt_log = settings.logs_dir / "backtest_trades.csv"
    if bt_log.exists():
        with open(bt_log, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["type"] = "trade"
                logs.append(row)

    # Sort by timestamp desc
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"logs": logs[:limit]}
