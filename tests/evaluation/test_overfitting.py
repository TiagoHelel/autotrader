"""Tests for src/evaluation/overfitting.py."""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import settings
from src.evaluation.overfitting import (
    OVERFIT_THRESHOLD,
    overfitting_score,
    save_validation_results,
    load_validation_results,
    get_latest_validation,
)


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    return tmp_path


class TestOverfittingScore:
    def test_gap_is_difference(self):
        assert overfitting_score(0.9, 0.8) == pytest.approx(0.1)

    def test_negative_gap_ok(self):
        # val > train: no overfit
        assert overfitting_score(0.7, 0.8) == pytest.approx(-0.1)

    def test_warning_when_over_threshold(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        overfitting_score(0.95, 0.70)  # gap=0.25 > 0.10
        assert any("Overfitting" in r.message for r in caplog.records)

    def test_ok_when_under_threshold(self, caplog):
        import logging
        caplog.set_level(logging.INFO)
        overfitting_score(0.80, 0.78)  # gap=0.02 < 0.10
        assert any("[OK]" in r.message for r in caplog.records)

    def test_threshold_constant(self):
        assert OVERFIT_THRESHOLD == 0.10


class TestSaveValidationResults:
    def _result(self, mean=0.7, std=0.05, folds=None):
        return {
            "mean_accuracy": mean,
            "std_accuracy": std,
            "fold_scores": [0.7, 0.72, 0.68],
            "fold_details": folds or [
                {"overfit_gap": 0.05}, {"overfit_gap": 0.08}, {"overfit_gap": 0.06},
            ],
        }

    def test_creates_parquet(self, fake_project):
        save_validation_results("EURUSD", {"xgboost": self._result()})
        f = settings.metrics_dir / "validation_results.parquet"
        assert f.exists()
        df = pd.read_parquet(f)
        assert len(df) == 1
        assert df.iloc[0]["model"] == "xgboost"
        assert df.iloc[0]["cpcv_score"] == pytest.approx(0.7)
        assert df.iloc[0]["overfit_gap"] == pytest.approx((0.05 + 0.08 + 0.06) / 3)
        assert df.iloc[0]["n_folds"] == 3

    def test_skips_model_without_mean_accuracy(self, fake_project):
        save_validation_results("EURUSD", {
            "bad": {"mean_accuracy": None, "std_accuracy": 0, "fold_details": []},
            "good": self._result(),
        })
        df = pd.read_parquet(settings.metrics_dir / "validation_results.parquet")
        assert list(df["model"]) == ["good"]

    def test_no_records_does_not_write(self, fake_project):
        save_validation_results("EURUSD", {"x": {"mean_accuracy": None}})
        assert not (settings.metrics_dir / "validation_results.parquet").exists()

    def test_appends_on_existing(self, fake_project):
        save_validation_results("EURUSD", {"xgboost": self._result()})
        save_validation_results("GBPUSD", {"linear": self._result(mean=0.65)})
        df = pd.read_parquet(settings.metrics_dir / "validation_results.parquet")
        assert len(df) == 2
        assert set(df["symbol"]) == {"EURUSD", "GBPUSD"}

    def test_empty_fold_details_gap_zero(self, fake_project):
        save_validation_results("EURUSD", {
            "x": {"mean_accuracy": 0.7, "std_accuracy": 0.01, "fold_details": []},
        })
        df = pd.read_parquet(settings.metrics_dir / "validation_results.parquet")
        assert df.iloc[0]["overfit_gap"] == 0.0
        assert df.iloc[0]["n_folds"] == 0


class TestLoadValidationResults:
    def test_missing_file_returns_empty(self, fake_project):
        assert load_validation_results().empty

    def test_filter_by_symbol_and_model(self, fake_project):
        save_validation_results("EURUSD", {
            "xgboost": {"mean_accuracy": 0.7, "std_accuracy": 0.01,
                        "fold_scores": [], "fold_details": [{"overfit_gap": 0.05}]},
            "linear": {"mean_accuracy": 0.6, "std_accuracy": 0.02,
                       "fold_scores": [], "fold_details": [{"overfit_gap": 0.03}]},
        })
        save_validation_results("GBPUSD", {
            "xgboost": {"mean_accuracy": 0.65, "std_accuracy": 0.01,
                        "fold_scores": [], "fold_details": [{"overfit_gap": 0.02}]},
        })
        all_df = load_validation_results()
        assert len(all_df) == 3
        eur = load_validation_results(symbol="EURUSD")
        assert len(eur) == 2
        xgb = load_validation_results(model="xgboost")
        assert len(xgb) == 2
        eur_xgb = load_validation_results(symbol="EURUSD", model="xgboost")
        assert len(eur_xgb) == 1


class TestGetLatestValidation:
    def test_empty_when_no_data(self, fake_project):
        assert get_latest_validation() == []

    def test_returns_latest_per_model(self, fake_project):
        # Two saves for same model — second should win
        save_validation_results("EURUSD", {
            "xgboost": {"mean_accuracy": 0.6, "std_accuracy": 0.01,
                        "fold_scores": [], "fold_details": [{"overfit_gap": 0.05}]},
        })
        save_validation_results("EURUSD", {
            "xgboost": {"mean_accuracy": 0.75, "std_accuracy": 0.01,
                        "fold_scores": [], "fold_details": [{"overfit_gap": 0.02}]},
        })
        latest = get_latest_validation("EURUSD")
        assert len(latest) == 1
        assert latest[0]["cpcv_score"] == pytest.approx(0.75)
