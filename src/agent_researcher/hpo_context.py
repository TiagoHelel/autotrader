"""
Loads HPO results as context for the LLM hypothesis generator.

Exposes two views:
- Champions: the currently promoted model params per (model, group)
- Top trials: the best N trials per study, for trend analysis
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def load_hpo_summary(top_n: int = 5) -> dict[str, Any]:
    """
    Returns a structured summary of HPO state for the LLM context.

    Structure:
    {
        "champions": [
            {
                "model_name": "xgboost",
                "symbol_group": "dollar_majors",
                "params": {...},
                "score": 0.72,
                "mean_accuracy": 0.73,
                "avg_overfit_gap": 0.03,
                "promoted_at": "...",
                "promotion_reason": "improvement",
            },
            ...
        ],
        "top_trials_by_study": {
            "hpo_xgboost_dollar_majors": [
                {"trial_number": 42, "score": 0.72, "params": {...}},
                ...
            ],
            ...
        },
        "param_patterns": [
            "xgboost/dollar_majors: max_depth median=3 (low complexity preferred)",
            ...
        ],
    }
    """
    try:
        from src.training.hpo_store import (
            HPO_MODELS,
            SYMBOL_GROUPS,
            get_top_trials,
            load_all_champions,
            study_name,
        )
    except ImportError:
        logger.warning("hpo_context: training module not available")
        return {}

    champions = load_all_champions()

    top_trials: dict[str, list[dict]] = {}
    for model_name in HPO_MODELS:
        for group_name in SYMBOL_GROUPS:
            sname = study_name(model_name, group_name)
            trials = get_top_trials(model_name, group_name, n=top_n)
            if trials:
                top_trials[sname] = trials

    param_patterns = _extract_param_patterns(top_trials)

    return {
        "champions": champions,
        "top_trials_by_study": top_trials,
        "param_patterns": param_patterns,
    }


def _extract_param_patterns(
    top_trials: dict[str, list[dict]],
) -> list[str]:
    """
    Summarize hyperparameter tendencies across top trials.
    Gives the LLM a compact signal: 'low max_depth wins in dollar_majors'.
    """
    import statistics

    patterns = []
    for study_key, trials in top_trials.items():
        if not trials:
            continue
        all_params = [t["params"] for t in trials if t.get("params")]
        if not all_params:
            continue
        for param_name in all_params[0]:
            values = [p[param_name] for p in all_params if param_name in p]
            if not values:
                continue
            try:
                median_val = statistics.median(values)
                patterns.append(f"{study_key}: {param_name} median={median_val:.4g}")
            except (TypeError, statistics.StatisticsError):
                pass

    return patterns
