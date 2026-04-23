"""Tests for src/evaluation/evaluator.py — valida previsoes vs candles reais."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.evaluation.evaluator import (
    evaluate_predictions,
    get_model_performance,
    get_performance_over_time,
    load_metrics,
)


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    settings.predictions_dir.mkdir(parents=True, exist_ok=True)
    settings.metrics_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


def _prediction(timestamp, model, current, t1, t2, t3):
    return {
        "timestamp": timestamp, "model": model, "current_price": current,
        "pred_t1": t1, "pred_t2": t2, "pred_t3": t3,
    }


def _raw(start="2025-01-02 00:00:00", n=10, start_price=1.1000, step=0.0001):
    times = pd.date_range(start, periods=n, freq="5min")
    closes = start_price + np.arange(n) * step
    return pd.DataFrame({"time": times, "open": closes, "high": closes, "low": closes, "close": closes})


class TestEvaluatePredictions:
    def test_no_prediction_file_returns_empty(self, fake_project):
        df = evaluate_predictions("EURUSD", _raw())
        assert df.empty

    def test_empty_predictions_returns_empty(self, fake_project):
        empty = pd.DataFrame(columns=["timestamp", "model", "current_price", "pred_t1", "pred_t2", "pred_t3"])
        empty.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        df = evaluate_predictions("EURUSD", _raw())
        assert df.empty

    def test_skips_when_future_candles_missing(self, fake_project):
        # Pred at t=now; raw has only 2 future candles (need 3)
        pred_time = "2025-01-02 00:00:00"
        preds = pd.DataFrame([_prediction(pred_time, "xgb", 1.1, 1.11, 1.12, 1.13)])
        preds.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        # raw has candle at same time + 2 future
        raw = _raw(start=pred_time, n=3)  # t, t+1, t+2 only 2 future
        result = evaluate_predictions("EURUSD", raw)
        # No metrics generated
        assert not (settings.metrics_dir / "EURUSD.parquet").exists()

    def test_computes_direction_and_errors(self, fake_project):
        pred_time = "2025-01-02 00:00:00"
        # current=1.1000, preds all up; actual closes rising
        preds = pd.DataFrame([_prediction(pred_time, "xgb", 1.1000, 1.1010, 1.1020, 1.1030)])
        preds.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        raw = _raw(start=pred_time, n=5, start_price=1.1000, step=0.0010)
        # future candles: t+1=1.1010, t+2=1.1020, t+3=1.1030, t+4=1.1040
        # evaluator picks first 3 candles after pred_time: 1.1010, 1.1020, 1.1030

        df = evaluate_predictions("EURUSD", raw)
        assert len(df) == 3
        # All directions up, all correct
        assert df["direction_correct"].sum() == 3
        # abs_error ~ 0 (perfect predictions)
        assert df["abs_error"].max() < 1e-9

    def test_skips_already_evaluated(self, fake_project):
        pred_time = "2025-01-02 00:00:00"
        preds = pd.DataFrame([_prediction(pred_time, "xgb", 1.1000, 1.1010, 1.1020, 1.1030)])
        preds.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        raw = _raw(start=pred_time, n=5, step=0.0010)
        first = evaluate_predictions("EURUSD", raw)
        second = evaluate_predictions("EURUSD", raw)
        # No new metrics appended
        assert len(first) == len(second) == 3

    def test_wrong_direction_counts_as_incorrect(self, fake_project):
        pred_time = "2025-01-02 00:00:00"
        # Predicted up, actual goes down
        preds = pd.DataFrame([_prediction(pred_time, "xgb", 1.1000, 1.1010, 1.1020, 1.1030)])
        preds.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        raw = _raw(start=pred_time, n=5, start_price=1.1000, step=-0.0010)
        df = evaluate_predictions("EURUSD", raw)
        # future candles fall: 1.099, 1.098, 1.097 — actual_direction=-1, pred_direction=+1
        assert df["direction_correct"].sum() == 0

    def test_pct_error_zero_when_actual_zero(self, fake_project):
        pred_time = "2025-01-02 00:00:00"
        preds = pd.DataFrame([_prediction(pred_time, "xgb", 1.0, 0.5, 0.5, 0.5)])
        preds.to_parquet(settings.predictions_dir / "EURUSD.parquet")
        times = pd.date_range(pred_time, periods=5, freq="5min")
        raw = pd.DataFrame({
            "time": times, "open": [1.0, 0, 0, 0, 0],
            "high": [1, 0, 0, 0, 0], "low": [1, 0, 0, 0, 0],
            "close": [1.0, 0.0, 0.0, 0.0, 0.0],
        })
        df = evaluate_predictions("EURUSD", raw)
        assert (df["pct_error"] == 0).all()


class TestGetModelPerformance:
    def test_no_metrics_dir_returns_empty(self, tmp_path, monkeypatch):
        # Point project_root somewhere with no metrics dir
        monkeypatch.setattr(settings, "project_root", tmp_path)
        assert get_model_performance().empty

    def test_aggregates_by_model(self, fake_project):
        metrics = pd.DataFrame([
            {"model": "xgb", "direction_correct": 1, "abs_error": 0.001, "pct_error": 0.1},
            {"model": "xgb", "direction_correct": 0, "abs_error": 0.002, "pct_error": 0.2},
            {"model": "linear", "direction_correct": 1, "abs_error": 0.003, "pct_error": 0.3},
        ])
        metrics.to_parquet(settings.metrics_dir / "EURUSD.parquet")
        perf = get_model_performance("EURUSD")
        assert set(perf["model"]) == {"xgb", "linear"}
        # linear 100% vs xgb 50% — sorted desc, linear first
        assert perf.iloc[0]["model"] == "linear"
        assert perf.iloc[0]["accuracy"] == pytest.approx(100.0)
        xgb_row = perf[perf["model"] == "xgb"].iloc[0]
        assert xgb_row["accuracy"] == pytest.approx(50.0)
        assert xgb_row["total_predictions"] == 2

    def test_aggregates_all_symbols(self, fake_project):
        pd.DataFrame([{"model": "xgb", "direction_correct": 1, "abs_error": 0.001, "pct_error": 0.1}]).to_parquet(
            settings.metrics_dir / "EURUSD.parquet"
        )
        pd.DataFrame([{"model": "xgb", "direction_correct": 0, "abs_error": 0.002, "pct_error": 0.2}]).to_parquet(
            settings.metrics_dir / "GBPUSD.parquet"
        )
        perf = get_model_performance()
        assert perf.iloc[0]["total_predictions"] == 2

    def test_no_files_returns_empty(self, fake_project):
        assert get_model_performance().empty


class TestPerformanceOverTime:
    def test_no_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        assert get_performance_over_time().empty

    def test_no_files_returns_empty(self, fake_project):
        assert get_performance_over_time().empty

    def test_rolling_columns(self, fake_project):
        rows = []
        for i in range(10):
            rows.append({
                "timestamp": pd.Timestamp("2025-01-02") + pd.Timedelta(minutes=i),
                "model": "xgb",
                "direction_correct": i % 2,
                "abs_error": 0.001 * i,
                "pct_error": 0.1 * i,
            })
        pd.DataFrame(rows).to_parquet(settings.metrics_dir / "EURUSD.parquet")
        df = get_performance_over_time("EURUSD")
        assert "rolling_accuracy" in df.columns
        assert "rolling_mae" in df.columns

    def test_filter_by_model(self, fake_project):
        rows = []
        for m in ("xgb", "linear"):
            for i in range(10):
                rows.append({
                    "timestamp": pd.Timestamp("2025-01-02") + pd.Timedelta(minutes=i),
                    "model": m, "direction_correct": 1,
                    "abs_error": 0.001, "pct_error": 0.1,
                })
        pd.DataFrame(rows).to_parquet(settings.metrics_dir / "EURUSD.parquet")
        df = get_performance_over_time(model="xgb")
        assert set(df["model"]) == {"xgb"}


class TestLoadMetrics:
    def test_missing_file_empty(self, fake_project):
        assert load_metrics("EURUSD").empty

    def test_loads_parquet(self, fake_project):
        pd.DataFrame([{"model": "x", "direction_correct": 1, "abs_error": 0.001, "pct_error": 0.1}]).to_parquet(
            settings.metrics_dir / "EURUSD.parquet"
        )
        df = load_metrics("EURUSD")
        assert len(df) == 1
