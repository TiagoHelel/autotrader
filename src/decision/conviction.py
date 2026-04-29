"""
Temporal conviction: are the model's last 3 "vintages" of prediction
for the same upcoming candle pointing in the same direction?

At time T, targeting candle T+1:
  - vintage T-2: pred_t3 from 2 cycles ago
  - vintage T-1: pred_t2 from 1 cycle ago
  - vintage T  : pred_t1 from this cycle

"high"    → all 3 agree on direction (all up or all down)
"low"     → at least one disagrees
"unknown" → fewer than 3 rows available or parquet missing
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def compute_temporal_conviction(
    symbol: str,
    model: str,
    pred_dir: Path,
) -> str:
    """Check if the last 3 prediction vintages agree on the T+1 candle direction."""
    filepath = pred_dir / f"{symbol}.parquet"
    if not filepath.exists():
        return "unknown"

    try:
        df = pd.read_parquet(filepath)
    except Exception as exc:
        logger.debug("temporal_conviction: could not read parquet for %s/%s: %s", symbol, model, exc)
        return "unknown"

    rows = df[df["model"] == model].tail(3).reset_index(drop=True)
    if len(rows) < 3:
        return "unknown"

    # T-2 vintage predicted T+1 as pred_t3; T-1 as pred_t2; T as pred_t1.
    dir_t3 = _direction(float(rows.loc[0, "pred_t3"]), float(rows.loc[0, "current_price"]))
    dir_t2 = _direction(float(rows.loc[1, "pred_t2"]), float(rows.loc[1, "current_price"]))
    dir_t1 = _direction(float(rows.loc[2, "pred_t1"]), float(rows.loc[2, "current_price"]))

    if dir_t3 == dir_t2 == dir_t1 and dir_t1 != 0:
        return "high"
    return "low"


def compute_all_convictions(
    symbol: str,
    models: list[str],
    pred_dir: Path,
) -> dict[str, str]:
    """Returns {model_name: conviction_str} for each model in the list."""
    return {m: compute_temporal_conviction(symbol, m, pred_dir) for m in models}


def _direction(pred: float, current_price: float) -> int:
    if pred > current_price:
        return 1
    if pred < current_price:
        return -1
    return 0
