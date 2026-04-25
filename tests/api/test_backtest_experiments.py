"""
Tests for src/api/backtest_experiments.py — all 12 endpoints.

Estratégia: mock das funções internas (backtest.engine, research.*, decision.*)
ao invés de criar dados em disco. Testa contrato HTTP: status, schema, filtros.
"""
from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.backtest_experiments import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ===================== /api/backtest/results =====================

class TestBacktestResults:
    def test_empty(self, client):
        with patch("src.backtest.engine.get_backtest_results", return_value=pd.DataFrame()):
            resp = client.get("/api/backtest/results")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trades"] == []
        assert body["count"] == 0

    def test_with_data(self, client):
        df = pd.DataFrame([
            {"timestamp": "2025-01-01", "model": "xgb", "pnl_pips": 10.0},
            {"timestamp": "2025-01-02", "model": "xgb", "pnl_pips": -5.0},
        ])
        with patch("src.backtest.engine.get_backtest_results", return_value=df):
            resp = client.get("/api/backtest/results?symbol=EURUSD&model=xgb")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2

    def test_limit(self, client):
        df = pd.DataFrame([
            {"timestamp": f"2025-01-{i:02d}", "model": "xgb", "pnl_pips": float(i)}
            for i in range(1, 11)
        ])
        with patch("src.backtest.engine.get_backtest_results", return_value=df):
            resp = client.get("/api/backtest/results?limit=3")
        assert resp.json()["count"] == 3


# ===================== /api/backtest/summary =====================

class TestBacktestSummary:
    def test_empty(self, client):
        with patch("src.backtest.engine.get_backtest_summary", return_value=[]):
            resp = client.get("/api/backtest/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"] == []
        assert body["count"] == 0

    def test_with_data(self, client):
        data = [{"model": "xgb", "symbol": "EURUSD", "pnl_total": 50.0}]
        with patch("src.backtest.engine.get_backtest_summary", return_value=data):
            resp = client.get("/api/backtest/summary")
        body = resp.json()
        assert body["count"] == 1
        assert body["summary"][0]["pnl_total"] == 50.0


# ===================== /api/backtest/run =====================

class TestBacktestRun:
    def test_with_symbol(self, client):
        with patch("src.backtest.engine.run_backtest_by_model"):
            resp = client.post("/api/backtest/run?symbol=EURUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["symbols"] == ["EURUSD"]

    def test_all_symbols(self, client):
        with patch("src.backtest.engine.run_backtest_by_model"):
            with patch("src.mt5.symbols.DESIRED_SYMBOLS", ["EURUSD", "GBPUSD"]):
                resp = client.post("/api/backtest/run")
        body = resp.json()
        assert body["status"] == "started"
        assert len(body["symbols"]) >= 2


# ===================== /api/backtest/equity =====================

class TestBacktestEquity:
    def test_no_dir(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        resp = client.get("/api/backtest/equity?symbol=EURUSD")
        assert resp.status_code == 200
        assert resp.json()["curves"] == {}

    def test_with_parquet(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        bt_dir = tmp_path / "data" / "backtest"
        bt_dir.mkdir(parents=True)
        pd.DataFrame([
            {"timestamp": "2025-01-01", "pnl_pips": 10.0},
            {"timestamp": "2025-01-02", "pnl_pips": 5.0},
        ]).to_parquet(bt_dir / "EURUSD_xgboost.parquet")
        # metrics file should be skipped
        pd.DataFrame([{"pnl_total": 15.0}]).to_parquet(bt_dir / "EURUSD_xgboost_metrics.parquet")

        resp = client.get("/api/backtest/equity?symbol=EURUSD")
        body = resp.json()
        assert "xgboost" in body["curves"]
        assert body["curves"]["xgboost"]["equity"] == [10.0, 15.0]

    def test_filter_by_model(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        bt_dir = tmp_path / "data" / "backtest"
        bt_dir.mkdir(parents=True)
        pd.DataFrame([{"timestamp": "t", "pnl_pips": 1.0}]).to_parquet(bt_dir / "EURUSD_xgboost.parquet")
        pd.DataFrame([{"timestamp": "t", "pnl_pips": 2.0}]).to_parquet(bt_dir / "EURUSD_linear.parquet")

        resp = client.get("/api/backtest/equity?symbol=EURUSD&model=xgboost")
        assert "linear" not in resp.json()["curves"]
        assert "xgboost" in resp.json()["curves"]


# ===================== /api/experiments/results =====================

class TestExperimentResults:
    def test_empty(self, client):
        with patch("src.research.feature_experiments.get_experiment_results", return_value=pd.DataFrame()):
            resp = client.get("/api/experiments/results")
        assert resp.json()["results"] == []

    def test_filters(self, client):
        df = pd.DataFrame([
            {"symbol": "EURUSD", "feature_set": "base", "model": "xgb", "score": 0.7},
            {"symbol": "GBPUSD", "feature_set": "full", "model": "rf", "score": 0.6},
        ])
        with patch("src.research.feature_experiments.get_experiment_results", return_value=df):
            resp = client.get("/api/experiments/results?symbol=EURUSD")
        assert resp.json()["count"] == 1

        with patch("src.research.feature_experiments.get_experiment_results", return_value=df):
            resp = client.get("/api/experiments/results?feature_set=full")
        assert resp.json()["count"] == 1

        with patch("src.research.feature_experiments.get_experiment_results", return_value=df):
            resp = client.get("/api/experiments/results?model=xgb")
        assert resp.json()["count"] == 1


# ===================== /api/experiments/ranking =====================

class TestExperimentRanking:
    def test_global_empty(self, client):
        with patch("src.research.model_ranking.rank_models", return_value=pd.DataFrame()):
            resp = client.get("/api/experiments/ranking")
        assert resp.json()["ranking"] == []

    def test_by_symbol(self, client):
        df = pd.DataFrame([{"model": "xgb", "score": 0.8}])
        with patch("src.research.model_ranking.rank_by_symbol", return_value=df):
            resp = client.get("/api/experiments/ranking?symbol=EURUSD")
        assert resp.json()["count"] == 1

    def test_global_with_data(self, client):
        df = pd.DataFrame([{"model": "xgb", "score": 0.8}, {"model": "rf", "score": 0.7}])
        with patch("src.research.model_ranking.rank_models", return_value=df):
            resp = client.get("/api/experiments/ranking")
        assert resp.json()["count"] == 2


# ===================== /api/experiments/ranking/feature-sets =====================

class TestFeatureSetRanking:
    def test_empty(self, client):
        with patch("src.research.model_ranking.rank_by_feature_set", return_value=pd.DataFrame()):
            resp = client.get("/api/experiments/ranking/feature-sets")
        assert resp.json()["ranking"] == []

    def test_with_data(self, client):
        df = pd.DataFrame([{"feature_set": "base", "score": 0.75}])
        with patch("src.research.model_ranking.rank_by_feature_set", return_value=df):
            resp = client.get("/api/experiments/ranking/feature-sets")
        assert resp.json()["count"] == 1


# ===================== /api/experiments/run =====================

class TestExperimentsRun:
    def test_with_symbol(self, client):
        with patch("src.research.feature_experiments.run_feature_experiments"):
            resp = client.post("/api/experiments/run?symbol=EURUSD")
        assert resp.json()["status"] == "started"
        assert resp.json()["symbol"] == "EURUSD"

    def test_all(self, client):
        with patch("src.research.feature_experiments.run_all_experiments"):
            resp = client.post("/api/experiments/run")
        assert resp.json()["symbol"] == "all"


# ===================== /api/models/best =====================

class TestModelsBest:
    def test_no_model(self, client):
        with patch("src.research.model_ranking.get_best_model", return_value=None):
            resp = client.get("/api/models/best")
        assert resp.json()["model"] is None

    def test_with_model(self, client):
        with patch("src.research.model_ranking.get_best_model", return_value={"model": "xgb", "score": 0.8}):
            resp = client.get("/api/models/best?symbol=EURUSD")
        body = resp.json()
        assert body["model"]["model"] == "xgb"

    def test_nan_cleaned(self, client):
        with patch("src.research.model_ranking.get_best_model", return_value={"model": "xgb", "score": float("nan")}):
            resp = client.get("/api/models/best")
        assert resp.json()["model"]["score"] == 0


# ===================== /api/models/by-regime =====================

class TestModelsByRegime:
    def test_returns_regimes(self, client):
        with patch("src.decision.model_selector.select_models_by_regime", return_value={"trending": "xgb"}):
            resp = client.get("/api/models/by-regime?symbol=EURUSD")
        body = resp.json()
        assert body["symbol"] == "EURUSD"
        assert body["regimes"]["trending"] == "xgb"


# ===================== /api/models/select =====================

class TestModelsSelect:
    def test_no_regime(self, client):
        with patch("src.decision.model_selector.select_model", return_value={"model": "xgb"}) as m:
            resp = client.get("/api/models/select?symbol=EURUSD")
        body = resp.json()
        assert body["symbol"] == "EURUSD"
        # Called with None regime when no query params
        m.assert_called_once_with("EURUSD", None)

    def test_with_regime(self, client):
        with patch("src.decision.model_selector.select_model", return_value={"model": "rf"}) as m:
            client.get("/api/models/select?symbol=EURUSD&trend=1&volatility_regime=2")
        m.assert_called_once_with("EURUSD", {"trend": 1, "volatility_regime": 2})


# ===================== /api/signals/latest =====================

class TestSignalsLatest:
    def test_no_files(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        resp = client.get("/api/signals/latest")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_signals_csv(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "signals.csv").write_text(
            "timestamp,symbol,model,signal,confidence,expected_return\n"
            "2025-01-02,EURUSD,xgb,BUY,0.8,0.002\n"
            "2025-01-01,EURUSD,xgb,SELL,0.6,-0.001\n"
        )
        resp = client.get("/api/signals/latest")
        data = resp.json()
        assert len(data) == 2
        # Sorted by timestamp desc
        assert data[0]["timestamp"] == "2025-01-02"
        assert data[0]["confidence"] == 0.8

    def test_filter_by_symbol(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "signals.csv").write_text(
            "timestamp,symbol,model,signal,confidence,expected_return\n"
            "2025-01-02,EURUSD,xgb,BUY,0.8,0.002\n"
            "2025-01-02,GBPUSD,xgb,SELL,0.6,-0.001\n"
        )
        resp = client.get("/api/signals/latest?symbol=EURUSD")
        assert len(resp.json()) == 1

    def test_decisions_csv_fallback(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "decisions.csv").write_text(
            "timestamp,symbol,action,details\n"
            '2025-01-02,EURUSD,signal_xgb,"signal=BUY conf=0.75 er=0.002"\n'
            '2025-01-02,EURUSD,other_action,"ignored"\n'
        )
        resp = client.get("/api/signals/latest")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["signal"] == "BUY"
        assert data[0]["confidence"] == 0.75

    def test_limit(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        lines = ["timestamp,symbol,model,signal,confidence,expected_return"]
        for i in range(10):
            lines.append(f"2025-01-{i+1:02d},EURUSD,xgb,BUY,0.8,0.002")
        (logs_dir / "signals.csv").write_text("\n".join(lines) + "\n")
        resp = client.get("/api/signals/latest?limit=3")
        assert len(resp.json()) == 3

    def test_bad_numeric_fields_default_to_zero(self, client, tmp_path, monkeypatch):
        from config.settings import settings
        monkeypatch.setattr(settings, "project_root", tmp_path)
        logs_dir = tmp_path / "data" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "signals.csv").write_text(
            "timestamp,symbol,model,signal,confidence,expected_return\n"
            "2025-01-02,EURUSD,xgb,BUY,bad,nope\n"
        )
        resp = client.get("/api/signals/latest")
        data = resp.json()
        assert data[0]["confidence"] == 0.0
        assert data[0]["expected_return"] == 0.0
