"""
Migracao idempotente do schema de data/predictions/*.parquet.

Adiciona as colunas novas (model_version, confidence, regime_*, session, etc.)
como NULL nas linhas antigas, para que o dataset fique uniforme antes de
subir pro S3.

Uso:
    python scripts/migrate_predictions_schema.py
    python scripts/migrate_predictions_schema.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402

NEW_COLUMNS: dict[str, object] = {
    "model_version": pd.NA,
    "input_window": pd.NA,
    "output_horizon": pd.NA,
    "features_hash": pd.NA,
    "confidence": pd.NA,
    "signal": pd.NA,
    "expected_return": pd.NA,
    "regime_trend": pd.NA,
    "regime_vol": pd.NA,
    "regime_range": pd.NA,
    "session": pd.NA,
    "session_score": pd.NA,
}

COLUMN_ORDER = [
    "timestamp", "symbol", "model", "model_version",
    "current_price", "pred_t1", "pred_t2", "pred_t3",
    "input_window", "output_horizon", "features_hash",
    "confidence", "signal", "expected_return",
    "regime_trend", "regime_vol", "regime_range",
    "session", "session_score",
]


def migrate_file(path: Path, dry_run: bool) -> dict:
    df = pd.read_parquet(path)
    added = [c for c in NEW_COLUMNS if c not in df.columns]
    for col in added:
        df[col] = NEW_COLUMNS[col]

    ordered = [c for c in COLUMN_ORDER if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    df = df[ordered + extra]

    if not dry_run and added:
        df.to_parquet(path, index=False)

    return {"file": path.name, "rows": len(df), "added": added}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pred_dir = settings.predictions_dir
    files = sorted(pred_dir.glob("*.parquet"))
    if not files:
        print(f"Nenhum arquivo em {pred_dir}")
        return

    print(f"{'DRY-RUN ' if args.dry_run else ''}Migrando {len(files)} arquivo(s) em {pred_dir}")
    for f in files:
        r = migrate_file(f, args.dry_run)
        status = "OK" if r["added"] else "ja migrado"
        print(f"  [{status}] {r['file']}  rows={r['rows']}  added={r['added']}")


if __name__ == "__main__":
    main()
