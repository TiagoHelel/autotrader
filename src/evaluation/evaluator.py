"""
Sistema de avaliacao de previsoes.
Compara previsoes com valores reais quando novos candles fecham.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)


def evaluate_predictions(symbol: str, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Avalia previsoes pendentes comparando com candles reais.

    Para cada previsao que ainda nao foi avaliada:
    - Verifica se os candles futuros (t+1, t+2, t+3) ja fecharam
    - Calcula metricas: direcao, erro absoluto, erro percentual

    Returns:
        DataFrame com metricas calculadas
    """
    pred_dir = settings.predictions_dir
    metrics_dir = settings.metrics_dir
    metrics_dir.mkdir(parents=True, exist_ok=True)

    pred_file = pred_dir / f"{symbol}.parquet"
    metrics_file = metrics_dir / f"{symbol}.parquet"

    if not pred_file.exists():
        return pd.DataFrame()

    predictions = pd.read_parquet(pred_file)
    if predictions.empty:
        return pd.DataFrame()

    # Carrega metricas existentes
    if metrics_file.exists():
        existing_metrics = pd.read_parquet(metrics_file)
        evaluated_keys = set(
            existing_metrics[["timestamp", "model"]].apply(
                lambda r: f"{r['timestamp']}_{r['model']}", axis=1
            )
        )
    else:
        existing_metrics = pd.DataFrame()
        evaluated_keys = set()

    raw_df = raw_df.sort_values("time").reset_index(drop=True)
    new_metrics = []

    for _, pred_row in predictions.iterrows():
        key = f"{pred_row['timestamp']}_{pred_row['model']}"
        if key in evaluated_keys:
            continue

        pred_time = pd.Timestamp(pred_row["timestamp"])
        current_price = pred_row["current_price"]

        # Encontra os candles futuros
        future_candles = raw_df[raw_df["time"] > pred_time].head(3)
        if len(future_candles) < 3:
            continue  # Candles futuros ainda nao fecharam

        actual_closes = future_candles["close"].values

        for horizon in range(3):
            h = horizon + 1
            pred_val = pred_row[f"pred_t{h}"]
            actual_val = actual_closes[horizon]

            # Direcao: comparar com preco atual
            pred_direction = 1 if pred_val > current_price else -1
            actual_direction = 1 if actual_val > current_price else -1
            direction_correct = int(pred_direction == actual_direction)

            # Erro absoluto
            abs_error = abs(pred_val - actual_val)

            # Erro percentual
            pct_error = abs_error / actual_val * 100 if actual_val != 0 else 0

            new_metrics.append({
                "timestamp": pred_row["timestamp"],
                "eval_time": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "model": pred_row["model"],
                "horizon": h,
                "predicted": pred_val,
                "actual": actual_val,
                "current_price": current_price,
                "direction_correct": direction_correct,
                "abs_error": abs_error,
                "pct_error": pct_error,
            })

    if new_metrics:
        new_df = pd.DataFrame(new_metrics)
        combined = pd.concat([existing_metrics, new_df], ignore_index=True)
        combined.to_parquet(metrics_file, index=False)
        logger.info(f"{symbol}: {len(new_metrics)} metricas avaliadas")
        return combined

    return existing_metrics


def get_model_performance(symbol: str = None) -> pd.DataFrame:
    """
    Retorna performance agregada dos modelos.
    Se symbol=None, agrega todos.
    """
    metrics_dir = settings.metrics_dir

    if not metrics_dir.exists():
        return pd.DataFrame()

    dfs = []
    if symbol:
        f = metrics_dir / f"{symbol}.parquet"
        if f.exists():
            dfs.append(pd.read_parquet(f))
    else:
        for f in metrics_dir.glob("*.parquet"):
            dfs.append(pd.read_parquet(f))

    if not dfs:
        return pd.DataFrame()

    all_metrics = pd.concat(dfs, ignore_index=True)

    # Agregar por modelo
    perf = all_metrics.groupby("model").agg(
        accuracy=("direction_correct", "mean"),
        mae=("abs_error", "mean"),
        mape=("pct_error", "mean"),
        total_predictions=("direction_correct", "count"),
        correct_predictions=("direction_correct", "sum"),
    ).reset_index()

    perf["accuracy"] = perf["accuracy"] * 100  # percentual
    perf = perf.sort_values("accuracy", ascending=False)

    return perf


def get_performance_over_time(symbol: str = None, model: str = None) -> pd.DataFrame:
    """Retorna performance ao longo do tempo (rolling window)."""
    metrics_dir = settings.metrics_dir

    if not metrics_dir.exists():
        return pd.DataFrame()

    dfs = []
    if symbol:
        f = metrics_dir / f"{symbol}.parquet"
        if f.exists():
            dfs.append(pd.read_parquet(f))
    else:
        for f in metrics_dir.glob("*.parquet"):
            dfs.append(pd.read_parquet(f))

    if not dfs:
        return pd.DataFrame()

    all_metrics = pd.concat(dfs, ignore_index=True)
    if model:
        all_metrics = all_metrics[all_metrics["model"] == model]

    all_metrics["timestamp"] = pd.to_datetime(all_metrics["timestamp"])
    all_metrics = all_metrics.sort_values("timestamp")

    # Rolling metrics por modelo (window=20)
    results = []
    for model_name, group in all_metrics.groupby("model"):
        group = group.sort_values("timestamp").reset_index(drop=True)
        group["rolling_accuracy"] = group["direction_correct"].rolling(20, min_periods=5).mean() * 100
        group["rolling_mae"] = group["abs_error"].rolling(20, min_periods=5).mean()
        results.append(group[["timestamp", "model", "rolling_accuracy", "rolling_mae"]])

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)


def load_metrics(symbol: str) -> pd.DataFrame:
    """Carrega metricas de um simbolo."""
    filepath = settings.metrics_dir / f"{symbol}.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)
