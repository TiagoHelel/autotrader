"""
Nightly HPO runner.

Iterates over (model_name x symbol_group) in round-robin, running N Optuna
trials per pair per call. Data is loaded from cached feature parquets — no
MT5 connection required.

Entry point for the scheduler:
    from src.training.hpo_runner import run_nightly_hpo
    run_nightly_hpo(n_trials_per_study=50)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.training.hpo_objective import build_objective
from src.training.hpo_store import (
    SYMBOL_GROUPS,
    HPO_MODELS,
    ensure_hpo_dirs,
    get_storage_url,
    get_trial_count,
    study_name,
)

logger = logging.getLogger(__name__)


def _load_xy_for_group(group_name: str) -> tuple[np.ndarray, np.ndarray] | None:
    """
    Load X, y for the representative symbol of a group (first available).
    Uses cached feature parquets — fails gracefully if no data yet.
    """
    from src.features.engineering import load_features, prepare_dataset

    for symbol in SYMBOL_GROUPS[group_name]:
        df = load_features(symbol)
        if df.empty:
            continue
        X, y, _ = prepare_dataset(df)
        if len(X) < 100:
            logger.warning("HPO: %s has only %d samples, skipping", symbol, len(X))
            continue
        logger.info("HPO: loaded %d samples from %s (group=%s)", len(X), symbol, group_name)
        return X, y

    logger.warning("HPO: no usable data for group %s", group_name)
    return None


def run_study(
    model_name: str,
    group_name: str,
    n_trials: int,
    X: np.ndarray,
    y: np.ndarray,
) -> dict[str, Any]:
    """Run N Optuna trials for one (model, group) pair."""
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    sname = study_name(model_name, group_name)
    storage = get_storage_url()

    study = optuna.create_study(
        direction="maximize",
        study_name=sname,
        storage=storage,
        load_if_exists=True,
    )
    objective = build_objective(model_name, X, y, group_name=group_name)

    prior_count = len(study.trials)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    new_trials = len(study.trials) - prior_count

    best = study.best_trial if study.best_trial else None
    result = {
        "study_name": sname,
        "model_name": model_name,
        "group_name": group_name,
        "new_trials": new_trials,
        "total_trials": len(study.trials),
        "best_score": best.value if best else None,
        "best_params": best.params if best else None,
    }
    logger.info(
        "HPO study=%s: +%d trials (total=%d) best_score=%.4f",
        sname,
        new_trials,
        result["total_trials"],
        result["best_score"] or 0,
    )
    return result


def run_nightly_hpo(n_trials_per_study: int = 50) -> list[dict[str, Any]]:
    """
    Main entry point for the scheduler.

    Runs N trials for each (model_name x symbol_group) combination.
    Groups without cached data are skipped gracefully.
    """
    ensure_hpo_dirs()
    results = []

    for model_name in HPO_MODELS:
        for group_name in SYMBOL_GROUPS:
            logger.info("HPO: starting %s / %s", model_name, group_name)
            xy = _load_xy_for_group(group_name)
            if xy is None:
                results.append({
                    "model_name": model_name,
                    "group_name": group_name,
                    "skipped": True,
                    "reason": "no_data",
                })
                continue

            X, y = xy
            try:
                result = run_study(model_name, group_name, n_trials_per_study, X, y)
                result["skipped"] = False
                results.append(result)
            except Exception:
                logger.exception("HPO: study failed for %s / %s", model_name, group_name)
                results.append({
                    "model_name": model_name,
                    "group_name": group_name,
                    "skipped": True,
                    "reason": "exception",
                })

    completed = sum(1 for r in results if not r.get("skipped"))
    logger.info("HPO nightly run done: %d/%d studies completed", completed, len(results))
    return results
