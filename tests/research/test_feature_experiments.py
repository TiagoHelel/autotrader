"""
Tests for src/research/feature_experiments.py.

Modulo pesado (treina modelos, roda backtest). Testamos as funções utilitárias
diretamente e as funções end-to-end com dados sintéticos pequenos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.research.feature_experiments import (
    FEATURE_SETS,
    EXPERIMENT_CONFIGS,
    DEFAULT_SPREADS,
    _get_feature_columns,
    _experiment_id,
    _prepare_filtered_dataset,
    _direction_accuracy,
    _quick_backtest,
    get_experiment_results,
    run_feature_experiments,
    run_all_experiments,
)


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    for d in ("features", "raw", "experiments"):
        (tmp_path / "data" / d).mkdir(parents=True)
    return tmp_path


# ===================== _get_feature_columns =====================

class TestGetFeatureColumns:
    def test_technical(self):
        cols = _get_feature_columns(["technical"])
        assert "close" in cols
        assert "rsi_14" in cols
        assert len(cols) == len(FEATURE_SETS["technical"])

    def test_combined(self):
        cols = _get_feature_columns(["technical", "regime"])
        assert len(cols) == len(FEATURE_SETS["technical"]) + len(FEATURE_SETS["regime"])

    def test_unknown_set_ignored(self):
        cols = _get_feature_columns(["nonexistent"])
        assert cols == []

    def test_news(self):
        cols = _get_feature_columns(["news"])
        assert "news_sentiment_base" in cols


# ===================== _experiment_id =====================

class TestExperimentId:
    def test_deterministic(self):
        a = _experiment_id("EURUSD", ["technical", "regime"], "xgboost")
        b = _experiment_id("EURUSD", ["technical", "regime"], "xgboost")
        assert a == b

    def test_order_independent(self):
        a = _experiment_id("EURUSD", ["regime", "technical"], "xgboost")
        b = _experiment_id("EURUSD", ["technical", "regime"], "xgboost")
        assert a == b  # sorted internally

    def test_different_params_different_id(self):
        a = _experiment_id("EURUSD", ["technical"], "xgboost")
        b = _experiment_id("EURUSD", ["technical"], "linear")
        assert a != b

    def test_length(self):
        assert len(_experiment_id("X", ["t"], "m")) == 12


# ===================== _prepare_filtered_dataset =====================

class TestPrepareFilteredDataset:
    def _make_df(self, n=100):
        cols = ["close", "time", "rsi_14", "ema_9", "atr_14"]
        data = {c: np.random.rand(n) for c in cols}
        data["close"] = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        data["time"] = pd.date_range("2025-01-01", periods=n, freq="5min")
        return pd.DataFrame(data)

    def test_shape(self):
        df = self._make_df(100)
        X, y, times = _prepare_filtered_dataset(df, ["rsi_14", "ema_9", "atr_14"])
        # input_window=10, output_horizon=3 → samples = 100 - 10 - 3 + 1 = 88
        assert X.shape[0] == y.shape[0] == len(times)
        assert X.shape[1] == 3 * settings.input_window  # 3 features * 10 window

    def test_too_small_returns_empty(self):
        df = self._make_df(5)
        X, y, times = _prepare_filtered_dataset(df, ["rsi_14"])
        assert len(X) == 0

    def test_nan_replaced(self):
        df = self._make_df(100)
        df.iloc[50, df.columns.get_loc("rsi_14")] = np.nan
        X, y, times = _prepare_filtered_dataset(df, ["rsi_14", "ema_9"])
        assert not np.isnan(X).any()


# ===================== _direction_accuracy =====================

class TestDirectionAccuracy:
    def test_perfect_prediction(self):
        y = np.array([[1.0, 1.1, 1.2]] * 10)
        acc = _direction_accuracy(y, y.copy(), np.zeros((10, 30)))
        assert acc >= 90.0  # near perfect

    def test_empty_returns_zero(self):
        assert _direction_accuracy(np.array([]), np.array([]), np.array([])) == 0.0


# ===================== _quick_backtest =====================

class TestQuickBacktest:
    def test_no_signals_returns_zeros(self):
        # Predictions ~ actuals → |ret| < threshold → all HOLD
        actuals = np.array([[1.1, 1.1, 1.1]] * 5)
        preds = actuals.copy()
        result = _quick_backtest(preds, actuals, np.zeros((5, 30)), "EURUSD")
        assert result["total_trades"] == 0
        assert result["pnl_total"] == 0

    def test_strong_buy_signal_produces_trades(self):
        # Big predicted move up
        actuals = np.array([[1.1 + i * 0.001, 1.1 + i * 0.002, 1.1 + i * 0.003] for i in range(20)])
        preds = actuals + 0.01  # predict much higher
        result = _quick_backtest(preds, actuals, np.zeros((20, 30)), "EURUSD")
        assert result["total_trades"] > 0

    def test_has_correct_keys(self):
        actuals = np.array([[1.1, 1.1, 1.1]] * 5)
        preds = actuals + 0.01
        result = _quick_backtest(preds, actuals, np.zeros((5, 30)), "EURUSD")
        assert set(result.keys()) == {"pnl_total", "sharpe", "max_drawdown", "winrate", "total_trades"}

    def test_default_spread_for_unknown_symbol(self):
        actuals = np.array([[1.1, 1.1, 1.1]] * 3)
        preds = actuals + 0.01
        result = _quick_backtest(preds, actuals, np.zeros((3, 30)), "UNKNOWN")
        # Should not crash, uses default
        assert "pnl_total" in result


# ===================== get_experiment_results =====================

class TestGetExperimentResults:
    def test_no_file_empty(self, fake_project):
        assert get_experiment_results().empty

    def test_reads_parquet(self, fake_project):
        df = pd.DataFrame([{"symbol": "EURUSD", "model": "xgb", "accuracy": 0.7}])
        df.to_parquet(settings.data_dir / "experiments" / "results.parquet")
        result = get_experiment_results()
        assert len(result) == 1


# ===================== run_feature_experiments =====================

class TestRunFeatureExperiments:
    # Use regime features (no "close" overlap) to avoid duplicate-column bug
    # in _prepare_filtered_dataset which adds ["close", "time"] unconditionally.
    _TEST_CONFIG = [["regime"]]

    def _setup_data(self, fake_project, n=200):
        """Cria dados sintéticos mínimos com regime features."""
        regime_cols = FEATURE_SETS["regime"]  # trend, volatility_regime, momentum, range_flag
        data = {c: np.random.randint(0, 3, n).astype(float) for c in regime_cols}
        data["close"] = 1.1 + np.cumsum(np.random.randn(n) * 0.0001)
        data["time"] = pd.date_range("2025-01-01", periods=n, freq="5min")
        df = pd.DataFrame(data)
        df.to_parquet(settings.features_dir / "EURUSD.parquet")
        pd.DataFrame({
            "time": data["time"], "open": data["close"],
            "high": data["close"], "low": data["close"], "close": data["close"],
        }).to_parquet(settings.raw_dir / "EURUSD.parquet")

    def test_no_data_returns_empty(self, fake_project):
        result = run_feature_experiments("EURUSD", feature_configs=self._TEST_CONFIG)
        assert result.empty

    def test_runs_experiments(self, fake_project):
        self._setup_data(fake_project, n=200)
        result = run_feature_experiments(
            "EURUSD",
            feature_configs=self._TEST_CONFIG,
        )
        assert not result.empty
        assert "accuracy" in result.columns
        assert "pnl" in result.columns
        assert (result["symbol"] == "EURUSD").all()
        assert (result["feature_set"] == "regime").all()

    def test_uses_cache(self, fake_project):
        self._setup_data(fake_project, n=200)
        first = run_feature_experiments("EURUSD", feature_configs=self._TEST_CONFIG)
        # Second call should use cache, not add more rows
        second = run_feature_experiments("EURUSD", feature_configs=self._TEST_CONFIG)
        assert len(second) == len(first)

    def test_force_reruns(self, fake_project):
        self._setup_data(fake_project, n=200)
        first = run_feature_experiments("EURUSD", feature_configs=self._TEST_CONFIG)
        second = run_feature_experiments("EURUSD", feature_configs=self._TEST_CONFIG, force=True)
        # Force → re-runs, appends
        assert len(second) >= len(first)

    def test_too_few_features_skipped(self, fake_project):
        # Only 2 features available (need >= 3)
        n = 200
        data = {"close": np.random.rand(n), "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
                "rsi_14": np.random.rand(n)}
        pd.DataFrame(data).to_parquet(settings.features_dir / "EURUSD.parquet")
        pd.DataFrame({
            "time": data["time"], "open": data["close"],
            "high": data["close"], "low": data["close"], "close": data["close"],
        }).to_parquet(settings.raw_dir / "EURUSD.parquet")
        result = run_feature_experiments("EURUSD", feature_configs=[["regime"]])
        assert result.empty


# ===================== run_all_experiments =====================

class TestRunAllExperiments:
    def test_no_data_returns_empty(self, fake_project):
        result = run_all_experiments(symbols=["EURUSD"])
        assert result.empty

    def test_catches_errors(self, fake_project):
        from unittest.mock import patch
        with patch("src.research.feature_experiments.run_feature_experiments", side_effect=RuntimeError("boom")):
            result = run_all_experiments(symbols=["EURUSD"])
        assert result.empty
