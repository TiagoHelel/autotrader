"""
HPO objective wrapper for Optuna.

Uso:
    study = optuna.create_study(direction="maximize")
    study.optimize(build_objective("xgboost", X, y), n_trials=100)

    # ou direto:
    best = run_hpo("xgboost", X, y, n_trials=100)
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np

from src.evaluation.cpcv import run_cpcv
from src.evaluation.overfitting import OVERFIT_THRESHOLD

logger = logging.getLogger(__name__)

# Penalidade aplicada por unidade de gap acima do threshold
_OVERFIT_PENALTY_MULTIPLIER = 2.0

# Hardcoded fallback ranges — used when no LLM-advised search space exists
_DEFAULT_SPACES: dict[str, dict[str, dict]] = {
    "xgboost": {
        "n_estimators":     {"type": "int",   "low": 50,    "high": 500},
        "max_depth":        {"type": "int",   "low": 2,     "high": 8},
        "learning_rate":    {"type": "float", "low": 0.01,  "high": 0.3,  "log": True},
        "subsample":        {"type": "float", "low": 0.5,   "high": 1.0},
        "colsample_bytree": {"type": "float", "low": 0.5,   "high": 1.0},
        "reg_lambda":       {"type": "float", "low": 0.1,   "high": 10.0, "log": True},
    },
    "random_forest": {
        "n_estimators":     {"type": "int",   "low": 50,    "high": 400},
        "max_depth":        {"type": "int",   "low": 3,     "high": 15},
        "min_samples_leaf": {"type": "int",   "low": 5,     "high": 50},
    },
    "linear": {
        "alpha":            {"type": "float", "low": 0.001, "high": 100.0, "log": True},
    },
}


def _suggest_from_space(trial, space: dict[str, dict]) -> dict:
    """Build Optuna suggestions from a param-spec dict."""
    params = {}
    for name, spec in space.items():
        ptype = spec.get("type", "float")
        low = spec["low"]
        high = spec["high"]
        use_log = bool(spec.get("log", False))
        if ptype == "int":
            params[name] = trial.suggest_int(name, int(low), int(high))
        else:
            params[name] = trial.suggest_float(name, float(low), float(high), log=use_log)
    return params


def _load_advised_space(model_name: str, group_name: str | None) -> dict[str, dict] | None:
    """Load LLM-advised search space if available, else return None."""
    if group_name is None:
        return None
    try:
        from src.agent_researcher.search_space_advisor import load_search_space
        return load_search_space(model_name, group_name)
    except Exception:
        return None


def _get_space(model_name: str, group_name: str | None) -> dict[str, dict]:
    """Return the active search space: LLM-advised if available, else defaults."""
    advised = _load_advised_space(model_name, group_name)
    if advised:
        # Merge: keep defaults for any param the LLM didn't advise on
        merged = dict(_DEFAULT_SPACES.get(model_name, {}))
        merged.update(advised)
        logger.debug("Using LLM-advised space for %s/%s (%d params)", model_name, group_name, len(advised))
        return merged
    return dict(_DEFAULT_SPACES.get(model_name, {}))


def _make_suggester(model_name: str, group_name: str | None) -> Callable:
    def suggest(trial) -> dict:
        space = _get_space(model_name, group_name)
        return _suggest_from_space(trial, space)
    return suggest


def _get_model_class(model_name: str):
    if model_name == "xgboost":
        from src.models.xgboost_model import XGBoostPredictor
        return XGBoostPredictor
    if model_name == "random_forest":
        from src.models.random_forest import RandomForestPredictor
        return RandomForestPredictor
    if model_name == "linear":
        from src.models.linear import LinearPredictor
        return LinearPredictor
    raise ValueError(f"Unknown model: {model_name!r}")


def evaluate_params(
    model_name: str,
    params: dict,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    embargo_pct: float = 0.02,
) -> dict:
    """
    Roda CPCV com os params dados e retorna métricas + score final.

    Returns:
        {
            "score": float,           # objetivo a maximizar (para Optuna)
            "mean_accuracy": float,
            "std_accuracy": float,
            "avg_overfit_gap": float,
            "overfit_warning": bool,
            "fold_details": list,
        }
    """
    model_class = _get_model_class(model_name)
    result = run_cpcv(model_class, params, X, y, n_splits=n_splits, embargo_pct=embargo_pct)

    gaps = [d.get("overfit_gap", 0.0) for d in result.get("fold_details", [])]
    avg_gap = float(np.mean(gaps)) if gaps else 0.0

    overfit_penalty = max(0.0, avg_gap - OVERFIT_THRESHOLD) * _OVERFIT_PENALTY_MULTIPLIER
    score = result["mean_accuracy"] - overfit_penalty

    return {
        "score": score,
        "mean_accuracy": result["mean_accuracy"],
        "std_accuracy": result["std_accuracy"],
        "avg_overfit_gap": avg_gap,
        "overfit_warning": avg_gap > OVERFIT_THRESHOLD,
        "fold_details": result.get("fold_details", []),
    }


def build_objective(
    model_name: str,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    embargo_pct: float = 0.02,
    group_name: str | None = None,
) -> Callable:
    """Retorna uma objective function pronta para passar ao Optuna.

    If group_name is provided, the LLM-advised search space for that
    (model, group) pair is used when available, falling back to defaults.
    """
    if model_name not in _DEFAULT_SPACES:
        raise ValueError(f"model_name deve ser um de: {list(_DEFAULT_SPACES)}")

    suggest = _make_suggester(model_name, group_name)

    def objective(trial) -> float:
        params = suggest(trial)
        metrics = evaluate_params(model_name, params, X, y, n_splits, embargo_pct)
        trial.set_user_attr("mean_accuracy", metrics["mean_accuracy"])
        trial.set_user_attr("avg_overfit_gap", metrics["avg_overfit_gap"])
        trial.set_user_attr("overfit_warning", metrics["overfit_warning"])
        logger.info(
            "[HPO] trial=%d model=%s group=%s score=%.4f acc=%.4f gap=%.4f params=%s",
            trial.number,
            model_name,
            group_name or "none",
            metrics["score"],
            metrics["mean_accuracy"],
            metrics["avg_overfit_gap"],
            params,
        )
        return metrics["score"]

    return objective


def run_hpo(
    model_name: str,
    X: np.ndarray,
    y: np.ndarray,
    n_trials: int = 50,
    n_splits: int = 5,
    embargo_pct: float = 0.02,
    study_name: str | None = None,
    storage: str | None = None,
    show_progress: bool = False,
) -> dict:
    """
    Roda um estudo Optuna completo e retorna os melhores params + métricas.

    Args:
        model_name: "xgboost" | "random_forest" | "linear"
        X, y: dados de treino
        n_trials: número de trials Optuna
        study_name: nome do estudo (para persistência com storage)
        storage: ex. "sqlite:///hpo.db" para persistir trials entre runs
        show_progress: exibe barra de progresso do Optuna

    Returns:
        {
            "best_params": dict,
            "best_score": float,
            "best_mean_accuracy": float,
            "best_avg_overfit_gap": float,
            "n_trials": int,
            "study_name": str,
        }
    """
    import optuna

    optuna.logging.set_verbosity(
        optuna.logging.INFO if show_progress else optuna.logging.WARNING
    )

    study = optuna.create_study(
        direction="maximize",
        study_name=study_name or f"hpo_{model_name}",
        storage=storage,
        load_if_exists=True,
    )
    objective = build_objective(model_name, X, y, n_splits, embargo_pct)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=show_progress)

    best = study.best_trial
    return {
        "best_params": best.params,
        "best_score": best.value,
        "best_mean_accuracy": best.user_attrs.get("mean_accuracy"),
        "best_avg_overfit_gap": best.user_attrs.get("avg_overfit_gap"),
        "n_trials": len(study.trials),
        "study_name": study.study_name,
    }
