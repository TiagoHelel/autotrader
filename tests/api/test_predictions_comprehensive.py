"""
Comprehensive tests for src/api/predictions.py endpoints.

Strategy:
- Monkeypatch settings.project_root → tmp_path to isolate file-system state.
- Write small synthetic parquets with pandas.
- Call endpoints via the session-scoped TestClient.
"""

from __future__ import annotations


import pandas as pd
import pytest

from config.settings import settings
from src.api import predictions as mod


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Redirects all settings paths to an isolated tmp tree."""
    monkeypatch.setattr(settings, "project_root", tmp_path)
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "predictions").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "metrics").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "logs").mkdir(parents=True, exist_ok=True)
    # Clear radar cache between tests
    mod._radar_cache["until"] = None
    mod._radar_cache["payload"] = None
    return tmp_path


def _write_predictions(path, rows):
    pd.DataFrame(rows).to_parquet(path, index=False)


# ========================= _finite_or =========================

class TestFiniteOr:
    def test_returns_value_when_finite(self):
        assert mod._finite_or(3.14) == 3.14

    def test_returns_default_for_nan(self):
        assert mod._finite_or(float("nan"), default=99) == 99

    def test_returns_default_for_inf(self):
        assert mod._finite_or(float("inf"), default=0.0) == 0.0

    def test_returns_default_on_conversion_error(self):
        assert mod._finite_or("abc", default=7) == 7
        assert mod._finite_or(None, default=7) == 7


# ========================= _sanitize_prediction_rows =========================

class TestSanitizePredictionRows:
    def test_empty_dataframe_returned_as_is(self):
        df = pd.DataFrame()
        result = mod._sanitize_prediction_rows(df)
        assert result.empty

    def test_nullifies_invalid_predictions(self):
        df = pd.DataFrame({
            "current_price": [1.0, 1.0, 1.0, 1.0],
            "pred_t1": [1.1, 0.1, 10.0, -5.0],  # valid, too-low, too-high, negative
            "pred_t2": [1.2, 1.3, 1.4, 1.5],
        })
        result = mod._sanitize_prediction_rows(df)
        assert result["pred_t1"].iloc[0] == 1.1
        assert pd.isna(result["pred_t1"].iloc[1])  # 0.1 < 1.0*0.2
        assert pd.isna(result["pred_t1"].iloc[2])  # 10 > 1.0*5
        assert pd.isna(result["pred_t1"].iloc[3])  # negative

    def test_returns_unchanged_when_no_current_price(self):
        df = pd.DataFrame({"pred_t1": [1.1, 1.2]})
        result = mod._sanitize_prediction_rows(df)
        # No current_price column → no filtering
        assert list(result["pred_t1"]) == [1.1, 1.2]


# ========================= /symbols =========================

class TestGetSymbols:
    def test_empty_raw_dir_returns_pending_symbols(self, client, fake_project):
        res = client.get("/api/predict/symbols")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] > 0
        # All symbols should be pending
        for s in data["symbols"]:
            assert s["status"] == "pending"
            assert s["candles"] == 0

    def test_with_active_parquet_marks_symbol_active(self, client, fake_project):
        raw_dir = fake_project / "data" / "raw"
        times = pd.to_datetime(["2026-04-16T10:00", "2026-04-16T10:05"])
        pd.DataFrame({
            "time": times,
            "close": [1.1, 1.11],
        }).to_parquet(raw_dir / "EURUSD.parquet", index=False)

        res = client.get("/api/predict/symbols")
        assert res.status_code == 200
        data = res.json()
        # Find EURUSD
        eur = [s for s in data["symbols"] if s["symbol"] == "EURUSD"][0]
        assert eur["status"] == "active"
        assert eur["candles"] == 2


# ========================= /predictions/latest =========================

class TestLatestPrediction:
    def test_invalid_symbol_returns_404(self, client, fake_project):
        res = client.get("/api/predict/predictions/latest?symbol=NOTREAL")
        assert res.status_code == 404

    def test_whitelisted_symbol_without_file_returns_empty(self, client, fake_project):
        res = client.get("/api/predict/predictions/latest?symbol=EURUSD")
        assert res.status_code == 200
        data = res.json()
        assert data["ensemble"] is None
        assert data["models"] == []
        assert data["n_models"] == 0

    def test_with_predictions_returns_ensemble_and_confidence(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgboost",
             "current_price": 1.10, "pred_t1": 1.11, "pred_t2": 1.12, "pred_t3": 1.13},
            {"timestamp": "2026-04-16T10:00", "model": "linear",
             "current_price": 1.10, "pred_t1": 1.12, "pred_t2": 1.13, "pred_t3": 1.14},
        ])
        res = client.get("/api/predict/predictions/latest?symbol=EURUSD")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "EURUSD"
        assert data["n_models"] == 2
        assert data["ensemble"]["pred_t1"] == pytest.approx(1.115)
        assert data["confidence"] is not None
        assert 0.0 <= data["confidence"] <= 1.0

    def test_with_empty_dataframe_returns_empty_shape(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        # Write empty parquet with correct schema
        pd.DataFrame({
            "timestamp": pd.Series([], dtype="object"),
            "model": pd.Series([], dtype="object"),
            "current_price": pd.Series([], dtype="float64"),
        }).to_parquet(pred_dir / "GBPUSD.parquet", index=False)

        res = client.get("/api/predict/predictions/latest?symbol=GBPUSD")
        assert res.status_code == 200
        assert res.json()["ensemble"] is None


# ========================= /predictions =========================

class TestListPredictions:
    def test_empty_dir_returns_empty(self, client, fake_project):
        # Empty dir is enough (fake_project already creates it)
        res = client.get("/api/predict/predictions")
        assert res.status_code == 200
        assert res.json()["predictions"] == []

    def test_filter_by_symbol(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 1.1, "pred_t1": 1.11, "pred_t2": 1.12, "pred_t3": 1.13},
        ])
        _write_predictions(pred_dir / "GBPUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 1.25, "pred_t1": 1.26, "pred_t2": 1.27, "pred_t3": 1.28},
        ])
        res = client.get("/api/predict/predictions?symbol=EURUSD")
        assert res.status_code == 200
        preds = res.json()["predictions"]
        assert len(preds) == 1
        # current_price should be from EURUSD
        assert preds[0]["current_price"] == pytest.approx(1.1)

    def test_filter_by_model(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 1.1, "pred_t1": 1.11, "pred_t2": 1.12, "pred_t3": 1.13},
            {"timestamp": "2026-04-16T10:00", "model": "linear",
             "current_price": 1.1, "pred_t1": 1.12, "pred_t2": 1.13, "pred_t3": 1.14},
        ])
        res = client.get("/api/predict/predictions?model=linear")
        assert res.status_code == 200
        preds = res.json()["predictions"]
        assert len(preds) == 1
        assert preds[0]["model"] == "linear"


# ========================= /signals/radar =========================

class TestRadarSignals:
    def test_all_symbols_hold_when_no_data(self, client, fake_project):
        res = client.get("/api/predict/signals/radar")
        assert res.status_code == 200
        data = res.json()
        for s in data["signals"]:
            assert s["signal"] == "HOLD"
            assert s["source"] == "no_data"

    def test_invalid_price_yields_hold(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 0.0, "pred_t1": 1.1, "pred_t2": 1.2, "pred_t3": 1.3},
        ])
        res = client.get("/api/predict/signals/radar")
        assert res.status_code == 200
        data = res.json()
        eur = [s for s in data["signals"] if s["symbol"] == "EURUSD"][0]
        assert eur["signal"] == "HOLD"
        assert eur["source"] == "invalid_price"

    def test_with_valid_predictions_produces_signal(self, client, fake_project):
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 1.10, "pred_t1": 1.15, "pred_t2": 1.16, "pred_t3": 1.17},
        ])
        res = client.get("/api/predict/signals/radar")
        assert res.status_code == 200
        data = res.json()
        eur = [s for s in data["signals"] if s["symbol"] == "EURUSD"][0]
        assert eur["source"] == "ensemble"
        assert eur["signal"] in ("BUY", "SELL", "HOLD")
        assert "breakdown" in data
        assert data["breakdown"]["BUY"] + data["breakdown"]["SELL"] + data["breakdown"]["HOLD"] == data["total"]

    def test_cache_is_used_on_second_call(self, client, fake_project):
        # First call populates cache
        client.get("/api/predict/signals/radar")
        # Change underlying data
        pred_dir = fake_project / "data" / "predictions"
        _write_predictions(pred_dir / "EURUSD.parquet", [
            {"timestamp": "2026-04-16T10:00", "model": "xgb",
             "current_price": 1.1, "pred_t1": 1.15, "pred_t2": 1.16, "pred_t3": 1.17},
        ])
        # Second call within TTL should still return cached empty-data payload
        res2 = client.get("/api/predict/signals/radar")
        data = res2.json()
        eur = [s for s in data["signals"] if s["symbol"] == "EURUSD"][0]
        # Cache hit → still "no_data" from first call
        assert eur["source"] == "no_data"

    def test_corrupted_parquet_produces_error_source(self, client, fake_project, monkeypatch):
        pred_dir = fake_project / "data" / "predictions"
        # Write a garbage file
        (pred_dir / "EURUSD.parquet").write_bytes(b"not a parquet")
        res = client.get("/api/predict/signals/radar")
        data = res.json()
        eur = [s for s in data["signals"] if s["symbol"] == "EURUSD"][0]
        assert eur["source"] == "error"


# ========================= /candles =========================

class TestGetCandles:
    def test_missing_file_returns_empty(self, client, fake_project):
        res = client.get("/api/predict/candles?symbol=EURUSD")
        assert res.status_code == 200
        assert res.json()["candles"] == []

    def test_returns_limited_sorted_candles(self, client, fake_project):
        raw_dir = fake_project / "data" / "raw"
        times = pd.to_datetime([f"2026-04-16T10:0{i}" for i in range(5)])
        pd.DataFrame({
            "time": times,
            "open": [1.0] * 5, "high": [1.1] * 5,
            "low": [0.9] * 5, "close": [1.05] * 5,
        }).to_parquet(raw_dir / "EURUSD.parquet", index=False)

        res = client.get("/api/predict/candles?symbol=EURUSD&limit=3")
        assert res.status_code == 200
        candles = res.json()["candles"]
        assert len(candles) == 3
        # Should be sorted ascending
        times_returned = [c["time"] for c in candles]
        assert times_returned == sorted(times_returned)


# ========================= /system/status =========================

class TestSystemStatus:
    def test_idle_when_no_data(self, client, fake_project):
        res = client.get("/api/predict/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "idle"
        assert data["active_symbols"] == 0
        assert data["total_predictions"] == 0
        assert data["last_update"] is None

    def test_running_with_data(self, client, fake_project):
        raw_dir = fake_project / "data" / "raw"
        pred_dir = fake_project / "data" / "predictions"
        pd.DataFrame({"time": pd.to_datetime(["2026-04-16"])}).to_parquet(
            raw_dir / "EURUSD.parquet", index=False)
        pd.DataFrame({"timestamp": ["2026-04-16T10:00"], "model": ["xgb"]}).to_parquet(
            pred_dir / "EURUSD.parquet", index=False)

        res = client.get("/api/predict/system/status")
        data = res.json()
        assert data["status"] == "running"
        assert data["active_symbols"] == 1
        assert data["total_predictions"] == 1
        assert data["last_update"] is not None


# ========================= /logs/recent =========================

class TestRecentLogs:
    def test_empty_when_no_logs(self, client, fake_project):
        res = client.get("/api/predict/logs/recent")
        assert res.status_code == 200
        assert res.json()["logs"] == []

    def test_aggregates_multiple_log_sources(self, client, fake_project):
        logs_dir = fake_project / "data" / "logs"

        # Create CSVs for each log type
        (logs_dir / "predictions.csv").write_text(
            "timestamp,symbol,model\n2026-04-16T10:00,EURUSD,xgb\n")
        (logs_dir / "decisions.csv").write_text(
            "timestamp,symbol,action\n2026-04-16T10:01,EURUSD,BUY\n")
        (logs_dir / "system.csv").write_text(
            "timestamp,level,module,message\n2026-04-16T10:02,INFO,m,boot\n")
        (logs_dir / "signals.csv").write_text(
            "timestamp,symbol,signal\n2026-04-16T10:03,EURUSD,BUY\n")
        (logs_dir / "session_metrics.csv").write_text(
            "timestamp,symbol,session\n2026-04-16T10:04,EURUSD,london\n")
        (logs_dir / "backtest_trades.csv").write_text(
            "timestamp,symbol,direction\n2026-04-16T10:05,EURUSD,LONG\n")

        res = client.get("/api/predict/logs/recent?limit=100")
        data = res.json()
        types = {row["type"] for row in data["logs"]}
        assert types == {"prediction", "decision", "system", "signal", "session", "trade"}
        # Should be sorted desc by timestamp → trade (latest) first
        assert data["logs"][0]["type"] == "trade"

    def test_respects_limit(self, client, fake_project):
        logs_dir = fake_project / "data" / "logs"
        rows = "timestamp,symbol\n" + "\n".join(
            f"2026-04-16T10:{i:02d},EURUSD" for i in range(20)
        )
        (logs_dir / "predictions.csv").write_text(rows + "\n")

        res = client.get("/api/predict/logs/recent?limit=5")
        assert len(res.json()["logs"]) == 5


# ========================= /models/performance/over-time =========================

class TestModelsOverTime:
    def test_returns_empty_when_no_metrics(self, client, fake_project):
        res = client.get("/api/predict/models/performance/over-time")
        assert res.status_code == 200
        assert res.json() == {"data": []}


# ========================= /experiments =========================

class TestExperiments:
    def test_returns_empty_when_no_experiments(self, client, fake_project):
        res = client.get("/api/predict/experiments")
        assert res.status_code == 200
        assert res.json() == {"experiments": []}

    def test_summary_empty(self, client, fake_project):
        res = client.get("/api/predict/experiments/summary")
        assert res.status_code == 200
        assert res.json() == {"summary": []}


# ========================= /models/feature-importance =========================

class TestFeatureImportance:
    def test_empty_when_no_data(self, client, fake_project):
        res = client.get("/api/predict/models/feature-importance")
        assert res.status_code == 200
        assert res.json() == {"importance": []}


# ========================= /models/validation =========================

class TestModelsValidation:
    def test_empty_when_no_results(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "get_latest_validation", lambda s=None: [])
        res = client.get("/api/predict/models/validation")
        assert res.status_code == 200
        data = res.json()
        assert data["validation"] == []
        assert "overfit_threshold" in data

    def test_adds_overfit_warning_flag(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "get_latest_validation", lambda s=None: [
            {"model": "xgb", "overfit_gap": 100.0, "fold_scores": [0.1]},
            {"model": "linear", "overfit_gap": 0.01},
        ])
        res = client.get("/api/predict/models/validation")
        data = res.json()
        assert data["validation"][0]["overfit_warning"] is True
        assert data["validation"][1]["overfit_warning"] is False
        # fold_scores should be stripped
        assert "fold_scores" not in data["validation"][0]


# ========================= /models/info =========================

class TestModelsInfo:
    def test_returns_models_list(self, client, fake_project):
        res = client.get("/api/predict/models/info")
        assert res.status_code == 200
        data = res.json()
        assert "models" in data
        # Each model should have name/params/features_used
        for m in data["models"]:
            assert "name" in m
            assert "params" in m
            assert "features_used" in m


# ========================= /metrics =========================

class TestMetrics:
    def test_empty_when_no_data(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "get_model_performance", lambda s=None: pd.DataFrame())
        res = client.get("/api/predict/metrics")
        assert res.status_code == 200
        assert res.json() == {"metrics": [], "global": {}}

    def test_global_stats_with_data(self, client, fake_project, monkeypatch):
        fake_perf = pd.DataFrame({
            "model": ["xgb", "linear"],
            "total_predictions": [100, 50],
            "correct_predictions": [60, 25],
            "mae": [0.01, 0.02],
            "mape": [0.5, 1.0],
        })
        monkeypatch.setattr(mod, "get_model_performance", lambda s=None: fake_perf)
        res = client.get("/api/predict/metrics")
        data = res.json()
        assert data["global"]["total_predictions"] == 150
        assert data["global"]["total_correct"] == 85
        assert data["global"]["global_accuracy"] == pytest.approx(85 / 150 * 100)


# ========================= /models/performance =========================

class TestModelsPerformance:
    def test_empty_when_no_data(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "get_model_performance", lambda: pd.DataFrame())
        res = client.get("/api/predict/models/performance")
        assert res.status_code == 200
        assert res.json() == {"ranking": []}

    def test_adds_rank_to_each_model(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "get_model_performance", lambda: pd.DataFrame({
            "model": ["xgb", "linear"],
            "accuracy": [0.7, 0.5],
        }))
        res = client.get("/api/predict/models/performance")
        ranking = res.json()["ranking"]
        assert ranking[0]["rank"] == 1
        assert ranking[1]["rank"] == 2


# ========================= /predictions/detail =========================

class TestPredictionsDetail:
    def test_empty_when_no_metrics(self, client, fake_project, monkeypatch):
        monkeypatch.setattr(mod, "load_metrics", lambda s: pd.DataFrame())
        res = client.get("/api/predict/predictions/detail?symbol=EURUSD")
        assert res.status_code == 200
        assert res.json() == {"data": []}

    def test_returns_sorted_head(self, client, fake_project, monkeypatch):
        fake_metrics = pd.DataFrame({
            "timestamp": ["2026-04-16T10:00", "2026-04-16T11:00", "2026-04-16T09:00"],
            "model": ["xgb"] * 3,
            "value": [1, 2, 3],
        })
        monkeypatch.setattr(mod, "load_metrics", lambda s: fake_metrics)
        res = client.get("/api/predict/predictions/detail?symbol=EURUSD&limit=2")
        data = res.json()["data"]
        assert len(data) == 2
        # Should be sorted desc
        assert data[0]["timestamp"] > data[1]["timestamp"]
