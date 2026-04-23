"""
Overfitting detection e tracking de validacao.
Compara train vs validation scores para detectar overfitting.
"""

import logging
from datetime import datetime

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

OVERFIT_THRESHOLD = 0.10  # gap > 10% = warning


def overfitting_score(train_score: float, val_score: float) -> float:
    """
    Calcula gap de overfitting.

    Args:
        train_score: accuracy no treino
        val_score: accuracy na validacao

    Returns:
        gap (train - val). Valores altos indicam overfitting.
    """
    gap = train_score - val_score

    if gap > OVERFIT_THRESHOLD:
        logger.warning(
            f"[WARNING] Overfitting detected: gap={gap:.4f} "
            f"(train={train_score:.4f}, val={val_score:.4f})"
        )
    else:
        logger.info(
            f"[OK] Overfit check: gap={gap:.4f} "
            f"(train={train_score:.4f}, val={val_score:.4f})"
        )

    return gap


def save_validation_results(symbol: str, cpcv_results: dict) -> None:
    """
    Salva resultados de validacao CPCV por simbolo/modelo.

    Args:
        symbol: par forex
        cpcv_results: dict {model_name: cpcv_result_dict}
    """
    metrics_dir = settings.metrics_dir
    metrics_dir.mkdir(parents=True, exist_ok=True)
    filepath = metrics_dir / "validation_results.parquet"

    timestamp = datetime.utcnow().isoformat()
    records = []

    for model_name, result in cpcv_results.items():
        mean_acc = result.get("mean_accuracy")
        std_acc = result.get("std_accuracy")

        if mean_acc is None:
            continue

        # Calcular overfit gap medio
        fold_details = result.get("fold_details", [])
        avg_overfit_gap = 0.0
        if fold_details:
            gaps = [d.get("overfit_gap", 0) for d in fold_details]
            avg_overfit_gap = sum(gaps) / len(gaps)

        records.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "model": model_name,
            "cpcv_score": mean_acc,
            "std": std_acc,
            "overfit_gap": avg_overfit_gap,
            "n_folds": len(fold_details),
            "fold_scores": str(result.get("fold_scores", [])),
        })

    if not records:
        return

    new_df = pd.DataFrame(records)

    if filepath.exists():
        existing = pd.read_parquet(filepath)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_parquet(filepath, index=False)
    logger.info(f"Validation results salvas: {symbol} | {len(records)} modelos")


def load_validation_results(symbol: str = None, model: str = None) -> pd.DataFrame:
    """Carrega resultados de validacao."""
    filepath = settings.metrics_dir / "validation_results.parquet"
    if not filepath.exists():
        return pd.DataFrame()

    df = pd.read_parquet(filepath)
    if symbol:
        df = df[df["symbol"] == symbol]
    if model:
        df = df[df["model"] == model]
    return df.sort_values("timestamp", ascending=False)


def get_latest_validation(symbol: str = None) -> list[dict]:
    """Retorna ultimo resultado de validacao por modelo."""
    df = load_validation_results(symbol)
    if df.empty:
        return []

    # Ultimo resultado por modelo
    latest = df.sort_values("timestamp", ascending=False).drop_duplicates(
        subset=["model"], keep="first"
    )

    return latest.to_dict(orient="records")
