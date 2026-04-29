"""
HPO persistence layer.

- Optuna studies stored in SQLite at data/hpo/studies.db
- Promoted champions stored as JSON in data/hpo/champions/
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HPO_DIR = PROJECT_ROOT / "data" / "hpo"
HPO_DB_PATH = HPO_DIR / "studies.db"
CHAMPIONS_DIR = HPO_DIR / "champions"

# Symbol groups for round-robin HPO. Representative symbol used for data loading.
SYMBOL_GROUPS: dict[str, list[str]] = {
    "yen_crosses": ["USDJPY", "EURJPY", "GBPJPY"],
    "dollar_majors": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"],
    "crosses": ["EURGBP"],
    "commodities": ["XAUUSD"],
}

# Maps each symbol to its group name
SYMBOL_TO_GROUP: dict[str, str] = {
    sym: group
    for group, symbols in SYMBOL_GROUPS.items()
    for sym in symbols
}

HPO_MODELS = ["xgboost", "random_forest"]

# Minimum trials before a study is eligible for promotion
MIN_TRIALS_FOR_PROMOTION = 20


def ensure_hpo_dirs() -> None:
    HPO_DIR.mkdir(parents=True, exist_ok=True)
    CHAMPIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_storage_url() -> str:
    ensure_hpo_dirs()
    return f"sqlite:///{HPO_DB_PATH}"


def study_name(model_name: str, group_name: str) -> str:
    return f"hpo_{model_name}_{group_name}"


def get_top_trials(
    model_name: str,
    group_name: str,
    n: int = 10,
) -> list[dict[str, Any]]:
    """Return the top-N trials for a study, sorted by score descending."""
    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        storage = get_storage_url()
        sname = study_name(model_name, group_name)
        study = optuna.load_study(study_name=sname, storage=storage)
        trials = [
            t for t in study.trials
            if t.state.name == "COMPLETE" and t.value is not None
        ]
        trials.sort(key=lambda t: t.value, reverse=True)
        return [
            {
                "trial_number": t.number,
                "score": t.value,
                "params": t.params,
                "mean_accuracy": t.user_attrs.get("mean_accuracy"),
                "avg_overfit_gap": t.user_attrs.get("avg_overfit_gap"),
                "overfit_warning": t.user_attrs.get("overfit_warning"),
            }
            for t in trials[:n]
        ]
    except Exception as exc:
        logger.debug("get_top_trials(%s, %s): %s", model_name, group_name, exc)
        return []


def get_best_params(model_name: str, group_name: str) -> dict[str, Any] | None:
    """Return params of the best trial, or None if no completed trials."""
    trials = get_top_trials(model_name, group_name, n=1)
    if not trials:
        return None
    return trials[0]["params"]


def get_trial_count(model_name: str, group_name: str) -> int:
    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        storage = get_storage_url()
        sname = study_name(model_name, group_name)
        study = optuna.load_study(study_name=sname, storage=storage)
        return len([t for t in study.trials if t.state.name == "COMPLETE"])
    except Exception:
        return 0


def save_champion(data: dict[str, Any]) -> None:
    """Persist a promoted champion to JSON."""
    ensure_hpo_dirs()
    fname = f"{data['model_name']}_{data['symbol_group']}.json"
    path = CHAMPIONS_DIR / fname
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Champion saved: %s", path)


def load_champion(model_name: str, symbol_group: str) -> dict[str, Any] | None:
    """Load the current champion for a model+group, or None."""
    path = CHAMPIONS_DIR / f"{model_name}_{symbol_group}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_all_champions() -> list[dict[str, Any]]:
    """Load every saved champion."""
    ensure_hpo_dirs()
    champions = []
    for path in sorted(CHAMPIONS_DIR.glob("*.json")):
        try:
            champions.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return champions


def get_best_params_for_symbol(model_name: str, symbol: str) -> dict[str, Any] | None:
    """Convenience: resolve symbol → group → champion params."""
    group = SYMBOL_TO_GROUP.get(symbol)
    if not group:
        return None
    champion = load_champion(model_name, group)
    if champion:
        return champion.get("params")
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
