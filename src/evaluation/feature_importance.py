"""
Feature importance tracking.
Salva importancia de features para XGBoost (gain) e Random Forest.
"""

import logging
from datetime import datetime

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)


def save_feature_importance(model, symbol: str, featured_df: pd.DataFrame) -> None:
    """
    Extrai e salva feature importance para um modelo.

    Suporta:
    - XGBoost: gain-based importance
    - Random Forest: feature_importances_ (impurity-based)
    """
    from src.features.engineering import ALL_FEATURE_COLUMNS

    available_cols = [c for c in ALL_FEATURE_COLUMNS if c in featured_df.columns]
    input_window = settings.input_window

    # Nomes das features (window flattened)
    feature_names = []
    for t in range(input_window):
        for col in available_cols:
            feature_names.append(f"{col}_t{t}")

    records = []
    timestamp = datetime.utcnow().isoformat()

    for horizon_idx, internal_model in enumerate(model._models):
        importances = None

        if model.name == "xgboost":
            try:
                importances = internal_model.feature_importances_
            except Exception:
                pass
        elif model.name == "random_forest":
            try:
                importances = internal_model.feature_importances_
            except Exception:
                pass

        if importances is None:
            continue

        # Agregar por feature base (somar across time windows)
        base_importance = {}
        for i, imp in enumerate(importances):
            if i < len(feature_names):
                base_name = feature_names[i].rsplit("_t", 1)[0]
                base_importance[base_name] = base_importance.get(base_name, 0.0) + float(imp)
            else:
                base_importance[f"feature_{i}"] = float(imp)

        for feat_name, imp_val in base_importance.items():
            records.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "model": model.name,
                "horizon": horizon_idx + 1,
                "feature": feat_name,
                "importance": imp_val,
            })

    if not records:
        return

    metrics_dir = settings.metrics_dir
    metrics_dir.mkdir(parents=True, exist_ok=True)
    filepath = metrics_dir / "feature_importance.parquet"

    new_df = pd.DataFrame(records)

    if filepath.exists():
        existing = pd.read_parquet(filepath)
        # Manter apenas ultimas entradas por symbol+model (evita crescimento infinito)
        existing = existing[
            ~((existing["symbol"] == symbol) & (existing["model"] == model.name))
        ]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_parquet(filepath, index=False)
    logger.info(f"Feature importance salva: {model.name} | {symbol} | {len(records)} features")


def load_feature_importance(symbol: str = None, model: str = None) -> pd.DataFrame:
    """Carrega feature importance."""
    filepath = settings.metrics_dir / "feature_importance.parquet"
    if not filepath.exists():
        return pd.DataFrame()

    df = pd.read_parquet(filepath)
    if symbol:
        df = df[df["symbol"] == symbol]
    if model:
        df = df[df["model"] == model]
    return df
