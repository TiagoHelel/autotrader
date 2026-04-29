from datetime import datetime, timedelta, timezone

import pytest

from src.training.hpo_store import save_champion, utc_now_iso
from src.training.promoter import (
    MAX_CHAMPION_DAYS,
    MIN_IMPROVEMENT,
    MIN_TRIALS_FOR_PROMOTION,
    _is_expired,
    evaluate_promotion,
    run_promotion_cycle,
)


def _trial(score: float = 0.72, overfit_warning: bool = False) -> dict:
    return {
        "trial_number": 1,
        "score": score,
        "params": {"max_depth": 3, "n_estimators": 150},
        "mean_accuracy": score + 0.01,
        "avg_overfit_gap": 0.03,
        "overfit_warning": overfit_warning,
    }


def _patch_store(monkeypatch, top_trials: list[dict], n_trials: int, tmp_path):
    monkeypatch.setattr("src.training.promoter.get_top_trials", lambda *a, **kw: top_trials)
    monkeypatch.setattr("src.training.promoter.get_trial_count", lambda *a: n_trials)
    monkeypatch.setattr("src.training.hpo_store.CHAMPIONS_DIR", tmp_path)
    monkeypatch.setattr("src.training.promoter.save_champion", lambda d: save_champion(d))
    monkeypatch.setattr("src.training.promoter.load_champion", lambda m, g: None)


def test_is_expired_returns_false_for_new_champion():
    champion = {"promoted_at": utc_now_iso()}
    assert _is_expired(champion) is False


def test_is_expired_returns_true_after_max_days():
    old_date = datetime.now(timezone.utc) - timedelta(days=MAX_CHAMPION_DAYS + 1)
    champion = {"promoted_at": old_date.isoformat()}
    assert _is_expired(champion) is True


def test_is_expired_handles_missing_key():
    assert _is_expired({}) is False


def test_evaluate_promotion_skips_when_too_few_trials(monkeypatch, tmp_path):
    _patch_store(monkeypatch, [_trial()], n_trials=MIN_TRIALS_FOR_PROMOTION - 1, tmp_path=tmp_path)
    result = evaluate_promotion("xgboost", "dollar_majors")
    assert result["action"] == "skipped"


def test_evaluate_promotion_rejects_overfit_challenger(monkeypatch, tmp_path):
    _patch_store(monkeypatch, [_trial(overfit_warning=True)], n_trials=MIN_TRIALS_FOR_PROMOTION, tmp_path=tmp_path)
    result = evaluate_promotion("xgboost", "dollar_majors")
    assert result["action"] == "rejected"
    assert "overfit_warning" in result["reason"]


def test_evaluate_promotion_first_promotion(monkeypatch, tmp_path):
    monkeypatch.setattr("src.training.promoter.get_top_trials", lambda *a, **kw: [_trial()])
    monkeypatch.setattr("src.training.promoter.get_trial_count", lambda *a: MIN_TRIALS_FOR_PROMOTION)
    monkeypatch.setattr("src.training.promoter.load_champion", lambda *a: None)
    saved = {}
    monkeypatch.setattr("src.training.promoter.save_champion", lambda d: saved.update(d))

    result = evaluate_promotion("xgboost", "dollar_majors")

    assert result["action"] == "promoted"
    assert result["reason"] == "first_promotion"
    assert saved["score"] == 0.72


def test_evaluate_promotion_promotes_when_improvement_sufficient(monkeypatch):
    current_champion = {
        "score": 0.70,
        "promoted_at": utc_now_iso(),
    }
    challenger = _trial(score=0.70 + MIN_IMPROVEMENT + 0.001)
    monkeypatch.setattr("src.training.promoter.get_top_trials", lambda *a, **kw: [challenger])
    monkeypatch.setattr("src.training.promoter.get_trial_count", lambda *a: MIN_TRIALS_FOR_PROMOTION)
    monkeypatch.setattr("src.training.promoter.load_champion", lambda *a: current_champion)
    saved = {}
    monkeypatch.setattr("src.training.promoter.save_champion", lambda d: saved.update(d))

    result = evaluate_promotion("xgboost", "dollar_majors")

    assert result["action"] == "promoted"
    assert result["reason"] == "improvement"


def test_evaluate_promotion_no_change_when_improvement_insufficient(monkeypatch):
    current_champion = {"score": 0.72, "promoted_at": utc_now_iso()}
    challenger = _trial(score=0.72 + MIN_IMPROVEMENT - 0.001)
    monkeypatch.setattr("src.training.promoter.get_top_trials", lambda *a, **kw: [challenger])
    monkeypatch.setattr("src.training.promoter.get_trial_count", lambda *a: MIN_TRIALS_FOR_PROMOTION)
    monkeypatch.setattr("src.training.promoter.load_champion", lambda *a: current_champion)

    result = evaluate_promotion("xgboost", "dollar_majors")

    assert result["action"] == "no_change"


def test_evaluate_promotion_promotes_expired_champion(monkeypatch):
    old_date = datetime.now(timezone.utc) - timedelta(days=MAX_CHAMPION_DAYS + 1)
    expired_champion = {"score": 0.99, "promoted_at": old_date.isoformat()}
    challenger = _trial(score=0.60)
    monkeypatch.setattr("src.training.promoter.get_top_trials", lambda *a, **kw: [challenger])
    monkeypatch.setattr("src.training.promoter.get_trial_count", lambda *a: MIN_TRIALS_FOR_PROMOTION)
    monkeypatch.setattr("src.training.promoter.load_champion", lambda *a: expired_champion)
    saved = {}
    monkeypatch.setattr("src.training.promoter.save_champion", lambda d: saved.update(d))

    result = evaluate_promotion("xgboost", "dollar_majors")

    assert result["action"] == "promoted"
    assert result["reason"] == "champion_expired"


def test_run_promotion_cycle_returns_result_per_combination(monkeypatch):
    monkeypatch.setattr(
        "src.training.promoter.evaluate_promotion",
        lambda model, group: {"action": "skipped", "reason": "test"},
    )
    from src.training.hpo_store import HPO_MODELS, SYMBOL_GROUPS

    results = run_promotion_cycle()

    assert len(results) == len(HPO_MODELS) * len(SYMBOL_GROUPS)
