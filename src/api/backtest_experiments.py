"""
FastAPI router para endpoints de backtest, experimentos, ranking e model selection.
"""

import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Query, BackgroundTasks

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest-experiments"])


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

@router.get("/api/backtest/results")
def get_backtest_results(
    symbol: str = Query(default=None),
    model: str = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """Trades simulados de backtest."""
    from src.backtest.engine import get_backtest_results as _get_results

    df = _get_results(symbol, model)
    if df.empty:
        return {"trades": [], "count": 0}

    df = df.sort_values("timestamp", ascending=False).head(limit)
    return {"trades": df.to_dict(orient="records"), "count": len(df)}


@router.get("/api/backtest/summary")
def get_backtest_summary():
    """Resumo de backtest por modelo/simbolo."""
    from src.backtest.engine import get_backtest_summary as _get_summary

    summaries = _get_summary()
    return {"summary": summaries, "count": len(summaries)}


@router.post("/api/backtest/run")
def run_backtest_endpoint(
    background_tasks: BackgroundTasks,
    symbol: str = Query(default=None),
):
    """Dispara backtest em background para um ou todos os simbolos."""
    from src.backtest.engine import run_backtest_by_model
    from src.mt5.symbols import DESIRED_SYMBOLS

    symbols = [symbol] if symbol else DESIRED_SYMBOLS

    def _run():
        for s in symbols:
            try:
                run_backtest_by_model(s)
            except Exception as e:
                logger.error(f"Backtest falhou para {s}: {e}")

    background_tasks.add_task(_run)
    return {"status": "started", "symbols": symbols}


@router.get("/api/backtest/equity")
def get_backtest_equity(
    symbol: str = Query(...),
    model: str = Query(default=None),
):
    """Equity curve de backtest."""
    bt_dir = settings.data_dir / "backtest"
    if not bt_dir.exists():
        return {"curves": {}}

    curves = {}
    pattern = f"{symbol}_*.parquet"
    for f in bt_dir.glob(pattern):
        if "_metrics" in f.stem:
            continue
        model_name = f.stem.replace(f"{symbol}_", "")
        if model and model_name != model:
            continue
        try:
            df = pd.read_parquet(f)
            if "pnl_pips" in df.columns:
                equity = df["pnl_pips"].cumsum().tolist()
                timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else list(range(len(equity)))
                curves[model_name] = {
                    "equity": equity,
                    "timestamps": timestamps,
                }
        except Exception:
            continue

    return {"curves": curves, "symbol": symbol}


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

@router.get("/api/experiments/results")
def get_experiment_results(
    symbol: str = Query(default=None),
    feature_set: str = Query(default=None),
    model: str = Query(default=None),
):
    """Resultados de feature experiments."""
    from src.research.feature_experiments import get_experiment_results

    df = get_experiment_results()
    if df.empty:
        return {"results": [], "count": 0}

    if symbol:
        df = df[df["symbol"] == symbol]
    if feature_set:
        df = df[df["feature_set"] == feature_set]
    if model:
        df = df[df["model"] == model]

    return {"results": df.to_dict(orient="records"), "count": len(df)}


@router.get("/api/experiments/ranking")
def get_experiment_ranking(
    symbol: str = Query(default=None),
):
    """Ranking de modelos baseado em experimentos."""
    from src.research.model_ranking import rank_models, rank_by_symbol

    if symbol:
        ranking = rank_by_symbol(symbol)
    else:
        ranking = rank_models()

    if ranking.empty:
        return {"ranking": [], "count": 0}

    return {"ranking": ranking.to_dict(orient="records"), "count": len(ranking)}


@router.get("/api/experiments/ranking/feature-sets")
def get_feature_set_ranking():
    """Ranking por feature set."""
    from src.research.model_ranking import rank_by_feature_set

    ranking = rank_by_feature_set()
    if ranking.empty:
        return {"ranking": [], "count": 0}

    return {"ranking": ranking.to_dict(orient="records"), "count": len(ranking)}


@router.post("/api/experiments/run")
def run_experiments_endpoint(
    background_tasks: BackgroundTasks,
    symbol: str = Query(default=None),
    force: bool = Query(default=False),
):
    """Dispara experimentos em background."""
    from src.research.feature_experiments import run_feature_experiments, run_all_experiments

    def _run():
        try:
            if symbol:
                run_feature_experiments(symbol, force=force)
            else:
                run_all_experiments(force=force)
        except Exception as e:
            logger.error(f"Experiments failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "started", "symbol": symbol or "all"}


# ---------------------------------------------------------------------------
# Model Selection
# ---------------------------------------------------------------------------

@router.get("/api/models/best")
def get_best_model(
    symbol: str = Query(default=None),
):
    """Retorna o melhor modelo global ou por simbolo."""
    from src.research.model_ranking import get_best_model as _get_best

    best = _get_best(symbol)
    if not best:
        return {"model": None}

    # Limpar valores nao serializaveis
    clean = {}
    for k, v in best.items():
        try:
            if isinstance(v, float) and (v != v):  # NaN check
                clean[k] = 0
            else:
                clean[k] = v
        except Exception:
            clean[k] = str(v)

    return {"model": clean}


@router.get("/api/models/by-regime")
def get_models_by_regime(
    symbol: str = Query(default="EURUSD"),
):
    """Retorna o melhor modelo para cada regime de um simbolo."""
    from src.decision.model_selector import select_models_by_regime

    results = select_models_by_regime(symbol)
    return {"symbol": symbol, "regimes": results}


@router.get("/api/models/select")
def select_model_endpoint(
    symbol: str = Query(default="EURUSD"),
    trend: int = Query(default=None),
    volatility_regime: int = Query(default=None),
    range_flag: int = Query(default=None),
):
    """Seleciona o melhor modelo dado regime atual."""
    from src.decision.model_selector import select_model

    regime = {}
    if trend is not None:
        regime["trend"] = trend
    if volatility_regime is not None:
        regime["volatility_regime"] = volatility_regime
    if range_flag is not None:
        regime["range_flag"] = range_flag

    result = select_model(symbol, regime or None)
    return {"selection": result, "symbol": symbol}


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@router.get("/api/signals/latest")
def get_latest_signals(
    symbol: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Sinais mais recentes (do log de sinais com dados estruturados)."""
    import csv

    signals = []

    # Primary source: signals.csv (structured: timestamp,symbol,model,signal,confidence,expected_return)
    sig_file = settings.logs_dir / "signals.csv"
    if sig_file.exists():
        with open(sig_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if symbol and row.get("symbol") != symbol:
                    continue
                # Ensure numeric fields
                try:
                    row["confidence"] = float(row.get("confidence", 0))
                except (ValueError, TypeError):
                    row["confidence"] = 0.0
                try:
                    row["expected_return"] = float(row.get("expected_return", 0))
                except (ValueError, TypeError):
                    row["expected_return"] = 0.0
                signals.append(row)

    # Fallback: decisions.csv (parse details text)
    if not signals:
        dec_file = settings.logs_dir / "decisions.csv"
        if dec_file.exists():
            with open(dec_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action = row.get("action", "")
                    if not action.startswith("signal_"):
                        continue
                    if symbol and row.get("symbol") != symbol:
                        continue
                    # Parse "signal=SELL conf=0.64 er=-0.001" from details
                    details = row.get("details", "")
                    parsed = {"timestamp": row.get("timestamp"), "symbol": row.get("symbol")}
                    parsed["model"] = action.replace("signal_", "")
                    for part in details.split():
                        if "=" in part:
                            k, v = part.split("=", 1)
                            if k == "signal":
                                parsed["signal"] = v
                            elif k == "conf":
                                try:
                                    parsed["confidence"] = float(v)
                                except ValueError:
                                    parsed["confidence"] = 0.0
                            elif k == "er":
                                try:
                                    parsed["expected_return"] = float(v)
                                except ValueError:
                                    parsed["expected_return"] = 0.0
                    signals.append(parsed)

    signals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return signals[:limit]
