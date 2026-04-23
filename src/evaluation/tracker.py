"""
Tracking de experimentos.
Registra modelos, parametros, features e performance historica.
"""

import json
import logging
from datetime import datetime

import pandas as pd

from config.settings import settings
from src.models.base import BasePredictor

logger = logging.getLogger(__name__)


def log_experiment(
    model: BasePredictor,
    symbol: str,
    train_size: int,
    metrics: dict = None,
) -> None:
    """
    Registra um experimento (treino de modelo).

    Args:
        model: instancia do modelo
        symbol: simbolo treinado
        train_size: tamanho do dataset de treino
        metrics: metricas opcionais (accuracy, MAE, MAPE)
    """
    exp_dir = settings.experiments_dir
    exp_dir.mkdir(parents=True, exist_ok=True)
    filepath = exp_dir / "experiments.parquet"

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "model": model.name,
        "params": json.dumps(model.params),
        "features_used": json.dumps(model.features_used),
        "train_size": train_size,
        "accuracy": metrics.get("accuracy") if metrics else None,
        "mae": metrics.get("mae") if metrics else None,
        "mape": metrics.get("mape") if metrics else None,
    }

    new_row = pd.DataFrame([record])

    if filepath.exists():
        existing = pd.read_parquet(filepath)
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row

    combined.to_parquet(filepath, index=False)
    logger.info(f"Experimento registrado: {model.name} | {symbol} | {train_size} amostras")


def get_experiments(model: str = None, symbol: str = None) -> pd.DataFrame:
    """Retorna historico de experimentos com filtros opcionais."""
    filepath = settings.experiments_dir / "experiments.parquet"
    if not filepath.exists():
        return pd.DataFrame()

    df = pd.read_parquet(filepath)

    if model:
        df = df[df["model"] == model]
    if symbol:
        df = df[df["symbol"] == symbol]

    return df.sort_values("timestamp", ascending=False).reset_index(drop=True)


def get_experiment_summary() -> pd.DataFrame:
    """Retorna resumo de todos os modelos testados."""
    filepath = settings.experiments_dir / "experiments.parquet"
    if not filepath.exists():
        return pd.DataFrame()

    df = pd.read_parquet(filepath)

    summary = df.groupby("model").agg(
        total_trainings=("timestamp", "count"),
        last_trained=("timestamp", "max"),
        avg_train_size=("train_size", "mean"),
        latest_accuracy=("accuracy", "last"),
        latest_mae=("mae", "last"),
        latest_mape=("mape", "last"),
        params=("params", "last"),
    ).reset_index()

    return summary
