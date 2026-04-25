"""
Tests for src/execution/engine.py — PredictionEngine.

Estratégia: mock pesado de dependências externas (MT5, modelos, features).
Testa contrato: _sanitize_prediction_array, _save_predictions, run_cycle flow.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.execution.engine import _sanitize_prediction_array, PredictionEngine


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    for d in ("predictions", "metrics", "features", "raw", "logs", "news"):
        (tmp_path / "data" / d).mkdir(parents=True)
    return tmp_path


# ===================== _sanitize_prediction_array =====================

class TestSanitizePredictionArray:
    def test_valid_prediction_unchanged(self):
        pred = np.array([[1.1010, 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        np.testing.assert_array_almost_equal(result, pred)

    def test_nan_replaced(self):
        pred = np.array([[float("nan"), 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result[0, 0] == 1.1000

    def test_inf_replaced(self):
        pred = np.array([[float("inf"), 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result[0, 0] == 1.1000

    def test_negative_replaced(self):
        pred = np.array([[-0.5, 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result[0, 0] == 1.1000

    def test_extreme_high_replaced(self):
        pred = np.array([[999.0, 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result[0, 0] == 1.1000  # > 5x current_price

    def test_extreme_low_replaced(self):
        pred = np.array([[0.05, 1.1020, 1.1030]])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result[0, 0] == 1.1000  # < 0.2x current_price

    def test_1d_reshaped(self):
        pred = np.array([1.1010, 1.1020, 1.1030])
        result = _sanitize_prediction_array(pred, 1.1000, "xgb")
        assert result.ndim == 2


# ===================== PredictionEngine =====================

class TestPredictionEngine:
    def test_init(self):
        engine = PredictionEngine(["EURUSD", "GBPUSD"])
        assert engine.symbols == ["EURUSD", "GBPUSD"]
        assert engine._cycle_count == 0

    def test_save_predictions(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        predictions = {
            "xgb": np.array([[1.1010, 1.1020, 1.1030]]),
            "linear": np.array([[1.1005, 1.1015, 1.1025]]),
        }
        engine._save_predictions("EURUSD", predictions, 1.1000)
        f = settings.predictions_dir / "EURUSD.parquet"
        assert f.exists()
        df = pd.read_parquet(f)
        assert len(df) == 2
        assert set(df["model"]) == {"xgb", "linear"}

    def test_save_predictions_appends(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        predictions = {"xgb": np.array([[1.1010, 1.1020, 1.1030]])}
        engine._save_predictions("EURUSD", predictions, 1.1000)
        engine._save_predictions("EURUSD", predictions, 1.1001)
        df = pd.read_parquet(settings.predictions_dir / "EURUSD.parquet")
        assert len(df) == 2

    def test_load_news_data_handles_error(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        with patch("src.execution.engine.load_news_raw", side_effect=RuntimeError("no news")):
            engine._load_news_data()
        assert engine._news_df.empty

    def test_add_news_features_empty_news(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._news_df = pd.DataFrame()
        df = pd.DataFrame({"time": pd.date_range("2025-01-01", periods=3, freq="5min"), "close": [1.1, 1.2, 1.3]})
        result = engine._add_news_features(df, "EURUSD")
        # Should have news columns filled with zeros
        from src.features.news_features import get_news_feature_columns
        for col in get_news_feature_columns():
            assert col in result.columns
            assert (result[col] == 0.0).all()

    @patch("src.execution.engine.run_cpcv")
    @patch("src.execution.engine.save_validation_results")
    @patch("src.execution.engine.overfitting_score")
    @patch("src.execution.engine.log_decision")
    def test_run_cpcv_validation(
        self,
        mock_log_decision,
        mock_ovf,
        mock_save,
        mock_cpcv,
        fake_project,
    ):
        mock_cpcv.return_value = {
            "mean_accuracy": 0.7,
            "std_accuracy": 0.05,
            "fold_scores": [0.7, 0.72],
            "fold_details": [
                {"train_score": 0.8, "val_score": 0.7, "overfit_gap": 0.1},
            ],
        }
        engine = PredictionEngine(["EURUSD"])
        X = np.random.rand(100, 50)
        y = np.random.rand(100, 3)
        result = engine._run_cpcv_validation("EURUSD", X, y)
        assert "xgboost" in result
        assert result["xgboost"]["avg_overfit_gap"] == pytest.approx(0.1)
        assert result["xgboost"]["overfit_warning"] is False
        mock_save.assert_called_once()
        mock_log_decision.assert_not_called()

    @patch("src.execution.engine.run_cpcv", side_effect=RuntimeError("fail"))
    @patch("src.execution.engine.save_validation_results")
    def test_run_cpcv_handles_failure(self, mock_save, mock_cpcv, fake_project):
        engine = PredictionEngine(["EURUSD"])
        result = engine._run_cpcv_validation("EURUSD", np.zeros((10, 5)), np.zeros((10, 3)))
        # Should not crash, returns results with None
        for v in result.values():
            assert v["mean_accuracy"] is None

    @patch("src.backtest.engine.run_backtest_by_model")
    def test_run_auto_backtest(self, mock_bt, fake_project):
        mock_bt.return_value = {
            "xgb": {"metrics": {"pnl_total": 50.0}},
        }
        engine = PredictionEngine(["EURUSD"])
        with patch("src.execution.engine.log_decision"):
            engine._run_auto_backtest("EURUSD")
        mock_bt.assert_called_once_with("EURUSD")

    @patch("src.backtest.engine.run_backtest_by_model", side_effect=RuntimeError("fail"))
    def test_run_auto_backtest_handles_error(self, mock_bt, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._run_auto_backtest("EURUSD")  # Should not raise


# ===================== Additional branch coverage =====================


def _make_featured_df(n: int = 60) -> pd.DataFrame:
    """DataFrame ja 'featurizado' para alimentar prepare_dataset/inference."""
    times = pd.date_range("2025-01-01", periods=n, freq="5min")
    rng = np.random.default_rng(42)
    close = 1.10 + rng.normal(0, 0.001, n).cumsum()
    return pd.DataFrame({
        "time": times,
        "open": close,
        "high": close + 0.0005,
        "low": close - 0.0005,
        "close": close,
        "volume": rng.integers(100, 500, n),
    })


class TestAddNewsFeaturesPopulated:
    """Cover the non-empty branch of _add_news_features."""

    def test_populated_news_merges_features(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._news_df = pd.DataFrame({
            "datetime": [pd.Timestamp("2025-01-01 00:00")],
            "currency": ["USD"],
            "impact_num": [3],
            "sentiment_basic": [1],
        })
        engine._llm_df = pd.DataFrame()
        df = pd.DataFrame({
            "time": pd.date_range("2025-01-01", periods=3, freq="5min"),
            "close": [1.1, 1.2, 1.3],
        })
        fake_feats = {col: 0.5 for col in
                     __import__("src.features.news_features", fromlist=["x"]).get_news_feature_columns()}
        with patch("src.execution.engine.build_news_features", return_value=fake_feats):
            result = engine._add_news_features(df, "EURUSD")
        # news columns present
        from src.features.news_features import get_news_feature_columns
        for col in get_news_feature_columns():
            assert col in result.columns

    def test_handles_nat_time(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._news_df = pd.DataFrame({
            "datetime": [pd.Timestamp("2025-01-01 00:00")],
            "currency": ["USD"],
            "impact_num": [3],
            "sentiment_basic": [1],
        })
        engine._llm_df = pd.DataFrame()
        df = pd.DataFrame({
            "time": [pd.NaT, pd.Timestamp("2025-01-01 00:05")],
            "close": [1.1, 1.2],
        })
        with patch("src.execution.engine.build_news_features", return_value={}):
            result = engine._add_news_features(df, "EURUSD")
        assert len(result) == 2

    def test_empty_df_with_empty_news_fills_zero(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._news_df = pd.DataFrame()
        df = pd.DataFrame()
        result = engine._add_news_features(df, "EURUSD")
        from src.features.news_features import get_news_feature_columns
        for col in get_news_feature_columns():
            assert col in result.columns


class TestLoadNewsData:
    def test_load_news_happy_path(self, fake_project):
        raw = pd.DataFrame({
            "country": ["United States"],
            "impact": [3],
            "signal": ["good"],
            "datetime": [pd.Timestamp("2025-01-01")],
        })
        engine = PredictionEngine(["EURUSD"])
        with patch("src.execution.engine.load_news_raw", return_value=raw), \
             patch("src.execution.engine.load_llm_features", return_value=pd.DataFrame({"a": [1]})):
            engine._load_news_data()
        assert not engine._news_df.empty
        assert not engine._llm_df.empty

    def test_load_news_empty_raw(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        with patch("src.execution.engine.load_news_raw", return_value=pd.DataFrame()), \
             patch("src.execution.engine.load_llm_features", return_value=pd.DataFrame()):
            engine._load_news_data()
        assert engine._news_df.empty
        assert engine._llm_df.empty


class TestSaveFeatureImportance:
    def test_calls_save_for_fitted_tree_models(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        m_xgb = MagicMock(name="xgb")
        m_xgb.is_fitted = True
        m_xgb.name = "xgboost"
        m_rf = MagicMock(name="rf")
        m_rf.is_fitted = True
        m_rf.name = "random_forest"
        m_lin = MagicMock(name="lin")
        m_lin.is_fitted = True
        m_lin.name = "linear"
        m_unfit = MagicMock(name="u")
        m_unfit.is_fitted = False
        m_unfit.name = "xgboost"
        engine.registry = MagicMock()
        engine.registry.get_models.return_value = [m_xgb, m_rf, m_lin, m_unfit]
        df = pd.DataFrame({"a": [1, 2]})
        with patch("src.execution.engine.save_feature_importance") as mock_save:
            engine._save_feature_importance("EURUSD", df)
        # xgb + rf only → 2 calls (linear and unfit skipped)
        assert mock_save.call_count == 2

    def test_handles_exception(self, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine.registry = MagicMock()
        engine.registry.get_models.side_effect = RuntimeError("fail")
        engine._save_feature_importance("EURUSD", pd.DataFrame())  # no raise


class TestRunCpcvValidationOverfitBranch:
    """Cover overfitting_score call inside fold_details loop."""

    @patch("src.execution.engine.log_decision")
    @patch("src.execution.engine.save_validation_results")
    @patch("src.execution.engine.overfitting_score", return_value=0.1)
    @patch("src.execution.engine.run_cpcv")
    def test_fold_details_triggers_overfit_score(
        self,
        mock_cpcv,
        mock_ovf,
        mock_save,
        mock_log_decision,
        fake_project,
    ):
        mock_cpcv.return_value = {
            "mean_accuracy": 0.6,
            "std_accuracy": 0.02,
            "fold_scores": [0.6],
            "fold_details": [
                {"train_score": 0.9, "val_score": 0.6, "overfit_gap": 0.3},
                {"train_score": 0.85, "val_score": 0.7, "overfit_gap": 0.15},
            ],
        }
        engine = PredictionEngine(["EURUSD"])
        result = engine._run_cpcv_validation(
            "EURUSD",
            np.zeros((30, 5)),
            np.zeros((30, 3)),
        )
        # called for each fold across 3 models
        assert mock_ovf.call_count == 6
        assert result["xgboost"]["avg_overfit_gap"] == pytest.approx((0.3 + 0.15) / 2)
        assert result["xgboost"]["overfit_warning"] is True
        mock_log_decision.assert_any_call(
            "EURUSD",
            "overfit_warning_xgboost",
            "avg_gap=0.2250 > threshold=0.1000",
        )

    @patch("src.execution.engine.log_decision")
    @patch("src.execution.engine.save_validation_results")
    @patch("src.execution.engine.overfitting_score", return_value=0.25)
    @patch("src.execution.engine.run_cpcv")
    def test_logs_warning_when_avg_gap_exceeds_threshold(
        self,
        mock_cpcv,
        mock_ovf,
        mock_save,
        mock_log_decision,
        fake_project,
        caplog,
    ):
        mock_cpcv.return_value = {
            "mean_accuracy": 0.6,
            "std_accuracy": 0.02,
            "fold_scores": [0.6],
            "fold_details": [
                {"train_score": 0.9, "val_score": 0.6, "overfit_gap": 0.3},
            ],
        }
        engine = PredictionEngine(["EURUSD"])

        with caplog.at_level("WARNING"):
            result = engine._run_cpcv_validation(
                "EURUSD",
                np.zeros((30, 5)),
                np.zeros((30, 3)),
            )

        assert result["xgboost"]["avg_overfit_gap"] == pytest.approx(0.3)
        assert result["xgboost"]["overfit_warning"] is True
        assert any("overfitting warning" in rec.message for rec in caplog.records)
        mock_log_decision.assert_any_call(
            "EURUSD",
            "overfit_warning_xgboost",
            "avg_gap=0.3000 > threshold=0.1000",
        )

    @patch("src.execution.engine.save_validation_results", side_effect=RuntimeError("disk full"))
    @patch("src.execution.engine.run_cpcv")
    def test_save_failure_is_swallowed(self, mock_cpcv, mock_save, fake_project):
        mock_cpcv.return_value = {"mean_accuracy": 0.5, "std_accuracy": 0.01, "fold_scores": [], "fold_details": []}
        engine = PredictionEngine(["EURUSD"])
        # should not raise
        engine._run_cpcv_validation("EURUSD", np.zeros((10, 3)), np.zeros((10, 3)))


class TestRunAutoBacktestEmpty:
    @patch("src.backtest.engine.run_backtest_by_model", return_value={})
    def test_empty_results_no_log(self, mock_bt, fake_project):
        engine = PredictionEngine(["EURUSD"])
        engine._run_auto_backtest("EURUSD")  # no raise


class TestRunCycle:
    """Integration-ish test of run_cycle with deep mocks."""

    def _setup_mocks(self, monkeypatch, featured_df=None):
        featured_df = featured_df if featured_df is not None else _make_featured_df()
        monkeypatch.setattr("src.execution.engine.is_market_open", lambda ts: True)
        monkeypatch.setattr("src.execution.engine.collect_update", lambda conn, syms: {s: featured_df for s in syms})
        monkeypatch.setattr("src.execution.engine.load_raw", lambda s: featured_df)
        monkeypatch.setattr("src.execution.engine.compute_features", lambda df: df)
        monkeypatch.setattr("src.execution.engine.add_session_features", lambda df, s: df)
        monkeypatch.setattr("src.execution.engine.save_features", lambda df, s: None)
        monkeypatch.setattr("src.execution.engine.get_current_regime", lambda df: {
            "trend_label": "up", "volatility_label": "low", "range_label": "tight",
        })
        monkeypatch.setattr("src.execution.engine.prepare_dataset", lambda df: (np.zeros((5, 3)), np.zeros((5, 3)), None))
        monkeypatch.setattr("src.execution.engine.prepare_inference_input",
                            lambda df: np.zeros((1, 3)))
        monkeypatch.setattr("src.execution.engine.get_current_session_info", lambda s: {
            "session_score": 1.0, "active_sessions": ["London"],
        })
        monkeypatch.setattr("src.execution.engine.generate_signals_for_models",
                            lambda preds, cp, session_score=None: {
                                name: {"signal": "HOLD", "confidence": 0.5, "expected_return": 0.0}
                                for name in preds
                            })
        monkeypatch.setattr("src.execution.engine.generate_ensemble_signal",
                            lambda sigs: {"signal": "HOLD", "confidence": 0.5, "expected_return": 0.0})
        monkeypatch.setattr("src.execution.engine.log_signal", lambda *a, **k: None)
        monkeypatch.setattr("src.execution.engine.log_prediction", lambda *a, **k: None)
        monkeypatch.setattr("src.execution.engine.log_decision", lambda *a, **k: None)
        monkeypatch.setattr("src.execution.engine.log_session_metrics", lambda **k: None)
        monkeypatch.setattr("src.execution.engine.evaluate_predictions",
                            lambda s, df: pd.DataFrame({"x": [1, 2]}))
        monkeypatch.setattr("src.execution.engine.log_experiment", lambda *a, **k: None)

    def test_run_cycle_happy_path(self, fake_project, monkeypatch):
        self._setup_mocks(monkeypatch)
        engine = PredictionEngine(["EURUSD"])
        # mock registry
        engine.registry = MagicMock()
        engine.registry.train_all.return_value = {"xgb": {"ok": True}}
        engine.registry.predict_all.return_value = {
            "xgb": np.array([[1.10, 1.11, 1.12]]),
        }
        m = MagicMock()
        m.is_fitted = True
        m.name = "xgboost"
        engine.registry.get_models.return_value = [m]

        with patch.object(engine, "_load_news_data"), \
             patch.object(engine, "_run_cpcv_validation",
                          return_value={"xgboost": {"mean_accuracy": 0.6, "std_accuracy": 0.02}}), \
             patch.object(engine, "_save_feature_importance"):
            result = engine.run_cycle(conn=MagicMock())

        assert result["cycle"] == 1
        assert "EURUSD" in result["symbols"]
        assert "predictions" in result["symbols"]["EURUSD"]

    def test_run_cycle_skips_when_market_closed(self, fake_project, monkeypatch):
        self._setup_mocks(monkeypatch)
        monkeypatch.setattr("src.execution.engine.is_market_open", lambda ts: False)
        engine = PredictionEngine(["EURUSD"])
        result = engine.run_cycle(conn=MagicMock())
        assert result.get("skipped") == "market_closed"
        assert result["symbols"] == {}

    def test_run_cycle_catches_symbol_exception(self, fake_project, monkeypatch):
        self._setup_mocks(monkeypatch)
        engine = PredictionEngine(["EURUSD"])
        with patch.object(engine, "_load_news_data"), \
             patch.object(engine, "_process_symbol", side_effect=RuntimeError("boom")):
            result = engine.run_cycle(conn=MagicMock())
        assert result["symbols"]["EURUSD"]["error"] == "boom"

    def test_process_symbol_empty_raw(self, fake_project, monkeypatch):
        monkeypatch.setattr("src.execution.engine.load_raw", lambda s: pd.DataFrame())
        engine = PredictionEngine(["EURUSD"])
        res = engine._process_symbol("EURUSD", None, MagicMock())
        assert res == {"error": "sem dados"}

    def test_process_symbol_insufficient_inference_data(self, fake_project, monkeypatch):
        self._setup_mocks(monkeypatch)
        monkeypatch.setattr("src.execution.engine.prepare_inference_input",
                            lambda df: np.array([]))
        engine = PredictionEngine(["EURUSD"])
        engine.registry = MagicMock()
        engine.registry.get_models.return_value = []
        with patch.object(engine, "_run_cpcv_validation", return_value={}), \
             patch.object(engine, "_save_feature_importance"):
            res = engine._process_symbol("EURUSD", _make_featured_df(), MagicMock())
        assert "error" in res
        assert "insuficientes" in res["error"]


class TestInitialSetup:
    def test_initial_setup_flow(self, fake_project, monkeypatch):
        df = pd.DataFrame({
            "time": pd.date_range("2025-01-01", periods=10, freq="5min"),
            "close": np.linspace(1.10, 1.11, 10),
        })
        monkeypatch.setattr("src.data.collector.collect_initial",
                            lambda conn, syms: {s: df for s in syms})
        monkeypatch.setattr("src.execution.engine.compute_features", lambda d: d)
        monkeypatch.setattr("src.execution.engine.add_session_features", lambda d, s: d)
        monkeypatch.setattr("src.execution.engine.save_features", lambda d, s: None)
        monkeypatch.setattr("src.execution.engine.prepare_dataset",
                            lambda d: (np.zeros((5, 3)), np.zeros((5, 3)), None))
        monkeypatch.setattr("src.execution.engine.log_experiment", lambda *a, **k: None)

        engine = PredictionEngine(["EURUSD"])
        engine.registry = MagicMock()
        engine.registry.train_all.return_value = {}
        m = MagicMock()
        m.is_fitted = True
        m.name = "xgboost"
        engine.registry.get_models.return_value = [m]

        with patch.object(engine, "_load_news_data"), \
             patch.object(engine, "_add_news_features", side_effect=lambda d, s: d), \
             patch.object(engine, "_run_cpcv_validation",
                          return_value={"xgboost": {"mean_accuracy": 0.6, "std_accuracy": 0.02}}), \
             patch.object(engine, "_save_feature_importance"):
            engine.initial_setup(MagicMock())

        assert "EURUSD" in engine._trained

    def test_initial_setup_empty_dataset(self, fake_project, monkeypatch):
        df = pd.DataFrame({"time": [pd.Timestamp("2025-01-01")], "close": [1.1]})
        monkeypatch.setattr("src.data.collector.collect_initial",
                            lambda conn, syms: {s: df for s in syms})
        monkeypatch.setattr("src.execution.engine.compute_features", lambda d: d)
        monkeypatch.setattr("src.execution.engine.add_session_features", lambda d, s: d)
        monkeypatch.setattr("src.execution.engine.save_features", lambda d, s: None)
        monkeypatch.setattr("src.execution.engine.prepare_dataset",
                            lambda d: (np.array([]), np.array([]), None))
        engine = PredictionEngine(["EURUSD"])
        engine.registry = MagicMock()
        with patch.object(engine, "_load_news_data"), \
             patch.object(engine, "_add_news_features", side_effect=lambda d, s: d):
            engine.initial_setup(MagicMock())
        assert "EURUSD" not in engine._trained
