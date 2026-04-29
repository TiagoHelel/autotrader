import numpy as np
import pytest

from src.training.hpo_objective import (
    _DEFAULT_SPACES,
    _get_space,
    _suggest_from_space,
    build_objective,
    evaluate_params,
)


def _make_xy(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    X = rng.standard_normal((n, 10))
    y = rng.standard_normal((n, 3))
    return X, y


class _FakeTrial:
    """Minimal Optuna trial stub."""

    def __init__(self, values: dict[str, float | int]) -> None:
        self._values = values
        self.number = 0
        self._user_attrs: dict = {}

    def suggest_int(self, name: str, low: int, high: int) -> int:
        return int(self._values.get(name, (low + high) // 2))

    def suggest_float(
        self,
        name: str,
        low: float,
        high: float,
        *,
        log: bool = False,
    ) -> float:
        return float(self._values.get(name, (low + high) / 2))

    def set_user_attr(self, key: str, value: object) -> None:
        self._user_attrs[key] = value


def test_default_spaces_contain_expected_models():
    assert "xgboost" in _DEFAULT_SPACES
    assert "random_forest" in _DEFAULT_SPACES
    assert "linear" in _DEFAULT_SPACES


def test_suggest_from_space_returns_all_params():
    space = _DEFAULT_SPACES["xgboost"]
    trial = _FakeTrial({})
    params = _suggest_from_space(trial, space)
    assert set(params.keys()) == set(space.keys())


def test_suggest_from_space_int_params_are_ints():
    space = {"n_estimators": {"type": "int", "low": 50, "high": 200}}
    trial = _FakeTrial({"n_estimators": 100})
    params = _suggest_from_space(trial, space)
    assert isinstance(params["n_estimators"], int)


def test_get_space_returns_defaults_when_no_advised(monkeypatch):
    monkeypatch.setattr(
        "src.training.hpo_objective._load_advised_space",
        lambda model, group: None,
    )
    space = _get_space("xgboost", "dollar_majors")
    assert space == _DEFAULT_SPACES["xgboost"]


def test_get_space_merges_advised_params(monkeypatch):
    advised = {"max_depth": {"type": "int", "low": 2, "high": 4}}
    monkeypatch.setattr(
        "src.training.hpo_objective._load_advised_space",
        lambda model, group: advised,
    )
    space = _get_space("xgboost", "dollar_majors")
    assert space["max_depth"] == advised["max_depth"]
    assert "learning_rate" in space


def test_build_objective_raises_for_unknown_model():
    X, y = _make_xy()
    with pytest.raises(ValueError, match="model_name"):
        build_objective("unknown_model", X, y)


def test_evaluate_params_returns_expected_keys():
    X, y = _make_xy()
    params = {"n_estimators": 10, "max_depth": 2, "min_samples_leaf": 20}
    result = evaluate_params("random_forest", params, X, y, n_splits=3)
    assert {"score", "mean_accuracy", "std_accuracy", "avg_overfit_gap", "overfit_warning"}.issubset(
        result.keys()
    )


def test_evaluate_params_score_penalises_overfit(monkeypatch):
    from src.evaluation.cpcv import run_cpcv

    def fake_cpcv(*args, **kwargs):
        return {
            "mean_accuracy": 0.70,
            "std_accuracy": 0.02,
            "fold_scores": [0.70],
            "fold_details": [
                {"fold": 1, "train_score": 0.95, "val_score": 0.70, "overfit_gap": 0.25}
            ],
        }

    monkeypatch.setattr("src.training.hpo_objective.run_cpcv", fake_cpcv)
    X, y = _make_xy()
    result = evaluate_params("random_forest", {"n_estimators": 10, "max_depth": 2}, X, y)
    assert result["overfit_warning"] is True
    assert result["score"] < result["mean_accuracy"]


def test_build_objective_callable_returns_float(monkeypatch):
    monkeypatch.setattr(
        "src.training.hpo_objective._load_advised_space",
        lambda model, group: None,
    )
    X, y = _make_xy()
    objective = build_objective("random_forest", X, y, n_splits=3, group_name="dollar_majors")
    trial = _FakeTrial({"n_estimators": 10, "max_depth": 3, "min_samples_leaf": 20})
    score = objective(trial)
    assert isinstance(score, float)
    assert "mean_accuracy" in trial._user_attrs
