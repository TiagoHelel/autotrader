"""
Champion/challenger promotion logic.

Rules:
- A study needs MIN_TRIALS_FOR_PROMOTION completed trials before any promotion.
- The best trial from the study is the "challenger".
- If no champion exists yet, the challenger is promoted immediately.
- If a champion exists, the challenger must exceed it by MIN_IMPROVEMENT.
- Champions with overfit_warning=True are never promoted.
- Champions older than MAX_CHAMPION_DAYS are retired and the challenger takes over.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.training.hpo_store import (
    HPO_MODELS,
    MIN_TRIALS_FOR_PROMOTION,
    SYMBOL_GROUPS,
    get_top_trials,
    get_trial_count,
    load_champion,
    save_champion,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

MIN_IMPROVEMENT = 0.005   # challenger must beat champion by at least 0.5pp
MAX_CHAMPION_DAYS = 60    # retire champion after this many days regardless


def _is_expired(champion: dict[str, Any]) -> bool:
    try:
        promoted_at = datetime.fromisoformat(champion["promoted_at"])
        age = datetime.now(timezone.utc) - promoted_at
        return age > timedelta(days=MAX_CHAMPION_DAYS)
    except (KeyError, ValueError):
        return False


def evaluate_promotion(
    model_name: str,
    group_name: str,
) -> dict[str, Any]:
    """
    Decide whether to promote a new champion for (model_name, group_name).

    Returns a dict describing the decision and outcome.
    """
    n_trials = get_trial_count(model_name, group_name)
    if n_trials < MIN_TRIALS_FOR_PROMOTION:
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "skipped",
            "reason": f"only {n_trials} trials (need {MIN_TRIALS_FOR_PROMOTION})",
        }

    top = get_top_trials(model_name, group_name, n=1)
    if not top:
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "skipped",
            "reason": "no completed trials",
        }

    challenger = top[0]

    if challenger.get("overfit_warning"):
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "rejected",
            "reason": "challenger has overfit_warning",
            "challenger_score": challenger["score"],
        }

    current = load_champion(model_name, group_name)

    # First promotion
    if current is None:
        _promote(model_name, group_name, challenger, role="champion", reason="first_promotion")
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "promoted",
            "reason": "first_promotion",
            "score": challenger["score"],
        }

    # Expired champion — promote challenger unconditionally
    if _is_expired(current):
        _promote(model_name, group_name, challenger, role="champion", reason="champion_expired")
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "promoted",
            "reason": "champion_expired",
            "previous_score": current.get("score"),
            "new_score": challenger["score"],
        }

    # Regular promotion: challenger must beat champion by MIN_IMPROVEMENT
    current_score = current.get("score", 0.0)
    improvement = challenger["score"] - current_score
    if improvement >= MIN_IMPROVEMENT:
        _promote(model_name, group_name, challenger, role="champion", reason="improvement")
        return {
            "model_name": model_name,
            "group_name": group_name,
            "action": "promoted",
            "reason": "improvement",
            "improvement": round(improvement, 4),
            "previous_score": current_score,
            "new_score": challenger["score"],
        }

    return {
        "model_name": model_name,
        "group_name": group_name,
        "action": "no_change",
        "reason": f"improvement {improvement:.4f} < threshold {MIN_IMPROVEMENT}",
        "current_score": current_score,
        "challenger_score": challenger["score"],
    }


def _promote(
    model_name: str,
    group_name: str,
    trial: dict[str, Any],
    role: str,
    reason: str,
) -> None:
    data = {
        "model_name": model_name,
        "symbol_group": group_name,
        "role": role,
        "params": trial["params"],
        "score": trial["score"],
        "mean_accuracy": trial.get("mean_accuracy"),
        "avg_overfit_gap": trial.get("avg_overfit_gap"),
        "trial_number": trial.get("trial_number"),
        "promoted_at": utc_now_iso(),
        "promotion_reason": reason,
    }
    save_champion(data)
    logger.info(
        "Promoted %s/%s: score=%.4f reason=%s",
        model_name,
        group_name,
        trial["score"],
        reason,
    )


def run_promotion_cycle() -> list[dict[str, Any]]:
    """
    Evaluate promotion for all (model x group) pairs.
    Called by the scheduler after each nightly HPO run.
    """
    results = []
    for model_name in HPO_MODELS:
        for group_name in SYMBOL_GROUPS:
            try:
                result = evaluate_promotion(model_name, group_name)
                results.append(result)
                action = result["action"]
                if action == "promoted":
                    logger.info(
                        "PROMOTED %s/%s: %s",
                        model_name,
                        group_name,
                        result.get("reason"),
                    )
            except Exception:
                logger.exception(
                    "Promotion check failed for %s/%s", model_name, group_name
                )
    return results
