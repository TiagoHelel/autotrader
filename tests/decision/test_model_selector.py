"""
Tests for src/decision/model_selector.py.

Estrategia: criamos um `project_root` sintetico em tmp_path com
`data/backtest/{symbol}_{model}.parquet` (trades) e `data/features/{symbol}.parquet`
(regime + session columns), e monkeypatchamos `settings.project_root` para ele.
Isso exercita `select_model`, `_select_by_regime`, `_select_by_session` e
`select_models_by_regime` sem depender do filesystem real do projeto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.decision import model_selector as ms


SYMBOL = "EURUSD"


def _make_trades(model: str, n: int, pnl_mean: float, start_ts: str = "2025-01-02 00:00:00") -> pd.DataFrame:
    """Gera N trades sequenciais (1 por hora) para um modelo."""
    rng = np.random.default_rng(hash(model) % (2**32))
    times = pd.date_range(start_ts, periods=n, freq="1h")
    return pd.DataFrame({
        "entry_time": times,
        "model": model,
        "pnl_pips": rng.normal(pnl_mean, 2.0, size=n),
    })


def _make_features(trade_frames: list[pd.DataFrame], regime_value: dict, session_values: dict) -> pd.DataFrame:
    """
    Cria um features.parquet que cobre o intervalo dos trades, com valores de
    regime e sessao fixos. `session_values` ex: {"london": 1, "new_york": 0}.
    `_select_by_regime` le colunas fixas: trend/volatility_regime/range_flag —
    sempre preencher as 3 (defaults 0) para nao quebrar o merge_asof.
    """
    all_trades = pd.concat(trade_frames, ignore_index=True)
    start = all_trades["entry_time"].min() - pd.Timedelta("1h")
    end = all_trades["entry_time"].max() + pd.Timedelta("1h")
    times = pd.date_range(start, end, freq="30min")

    df = pd.DataFrame({"time": times})
    # defaults para todas as colunas de regime lidas pelo modulo
    for col in ("trend", "volatility_regime", "range_flag"):
        df[col] = 0
    for k, v in regime_value.items():
        df[k] = v
    for s, v in session_values.items():
        df[f"session_{s}"] = v
    return df


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Monta data/backtest + data/features em tmp_path e redireciona settings."""
    (tmp_path / "data" / "backtest").mkdir(parents=True)
    (tmp_path / "data" / "features").mkdir(parents=True)
    monkeypatch.setattr(settings, "project_root", tmp_path)

    def _write(trades_by_model: dict, regime: dict, sessions: dict):
        frames = []
        for model, df in trades_by_model.items():
            frames.append(df)
            df.to_parquet(tmp_path / "data" / "backtest" / f"{SYMBOL}_{model}.parquet")
        feats = _make_features(frames, regime, sessions)
        feats.to_parquet(tmp_path / "data" / "features" / f"{SYMBOL}.parquet")
        return tmp_path

    return _write


# -------------------- _select_by_regime --------------------

class TestSelectByRegime:
    def test_picks_model_with_highest_pnl_in_regime(self, fake_project):
        fake_project(
            trades_by_model={
                "xgboost": _make_trades("xgboost", n=20, pnl_mean=5.0),
                "random_forest": _make_trades("random_forest", n=20, pnl_mean=1.0),
            },
            regime={"trend": 1},
            sessions={"london": 0},
        )
        result = ms._select_by_regime(SYMBOL, {"trend": 1})
        assert result is not None
        assert result["model"] == "xgboost"
        assert result["regime_match"] is True
        assert result["session_match"] is False
        assert result["score"] > 0
        assert "best in regime" in result["reason"]

    def test_returns_none_when_no_backtest_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)  # sem pastas
        assert ms._select_by_regime(SYMBOL, {"trend": 1}) is None

    def test_returns_none_when_no_features_file(self, tmp_path, monkeypatch):
        (tmp_path / "data" / "backtest").mkdir(parents=True)
        _make_trades("xgboost", n=5, pnl_mean=1.0).to_parquet(
            tmp_path / "data" / "backtest" / f"{SYMBOL}_xgboost.parquet"
        )
        monkeypatch.setattr(settings, "project_root", tmp_path)
        assert ms._select_by_regime(SYMBOL, {"trend": 1}) is None

    def test_ignores_metrics_files(self, fake_project, tmp_path):
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=10, pnl_mean=3.0)},
            regime={"trend": 1},
            sessions={"london": 0},
        )
        # adicionar um "_metrics" garbage que, se lido, quebraria
        (tmp_path / "data" / "backtest" / f"{SYMBOL}_metrics.parquet").write_bytes(b"garbage")
        # nao deve levantar
        result = ms._select_by_regime(SYMBOL, {"trend": 1})
        assert result is not None
        assert result["model"] == "xgboost"


# -------------------- _select_by_session --------------------

class TestSelectBySession:
    def test_picks_best_model_in_session(self, fake_project):
        fake_project(
            trades_by_model={
                "xgboost": _make_trades("xgboost", n=20, pnl_mean=4.0),
                "linear": _make_trades("linear", n=20, pnl_mean=0.5),
            },
            regime={"trend": 0},
            sessions={"london": 1},
        )
        result = ms._select_by_session(SYMBOL, "london")
        assert result is not None
        assert result["model"] == "xgboost"
        assert result["session_match"] is True
        assert result["regime_match"] is False
        assert result["trades"] >= 5
        assert "session=london" in result["reason"]

    def test_enforces_minimum_trade_count(self, fake_project):
        """Menos de 5 trades na sessao → sem modelo elegivel."""
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=3, pnl_mean=10.0)},
            regime={"trend": 0},
            sessions={"london": 1},
        )
        result = ms._select_by_session(SYMBOL, "london")
        assert result is None

    def test_returns_none_when_session_col_missing(self, fake_project):
        """Se session_col nao existe no features.parquet, retorna None."""
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=10, pnl_mean=3.0)},
            regime={"trend": 0},
            sessions={"london": 1},  # nao cria "tokyo"
        )
        assert ms._select_by_session(SYMBOL, "tokyo") is None

    def test_session_with_regime_filter(self, fake_project):
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=20, pnl_mean=3.0)},
            regime={"trend": 1, "volatility_regime": 2},
            sessions={"london": 1},
        )
        result = ms._select_by_session(SYMBOL, "london", regime={"trend": 1})
        assert result is not None
        assert result["regime_match"] is True
        assert result["session_match"] is True


# -------------------- select_model (4-tier fallback) --------------------

class TestSelectModel:
    def test_tier1_session_plus_regime_preferred(self, fake_project):
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=20, pnl_mean=4.0)},
            regime={"trend": 1},
            sessions={"london": 1},
        )
        result = ms.select_model(SYMBOL, regime={"trend": 1}, session="london")
        assert result["model"] == "xgboost"
        assert result["session_match"] is True
        assert result["regime_match"] is True

    def test_tier4_hard_default_when_nothing_found(self, tmp_path, monkeypatch):
        """Sem backtest, sem features, sem rankings → default xgboost."""
        monkeypatch.setattr(settings, "project_root", tmp_path)
        # mock get_best_model pra retornar None
        monkeypatch.setattr(ms, "get_best_model", lambda sym: None)
        result = ms.select_model(SYMBOL)
        assert result["model"] == "xgboost"
        assert result["reason"] == "default fallback"
        assert result["regime_match"] is False
        assert result["session_match"] is False

    def test_tier4_best_overall_when_only_ranking_available(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        monkeypatch.setattr(ms, "get_best_model", lambda sym: {"model": "random_forest", "score": 0.73})
        result = ms.select_model(SYMBOL)
        assert result["model"] == "random_forest"
        assert result["score"] == pytest.approx(0.73)
        assert result["reason"] == "best overall score"

    def test_returns_all_required_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        monkeypatch.setattr(ms, "get_best_model", lambda sym: None)
        result = ms.select_model(SYMBOL)
        for key in ("model", "score", "reason", "regime_match", "session_match"):
            assert key in result


# -------------------- select_models_by_regime --------------------

class TestSelectModelsByRegime:
    def test_returns_entry_for_every_canonical_regime(self, fake_project):
        fake_project(
            trades_by_model={"xgboost": _make_trades("xgboost", n=20, pnl_mean=3.0)},
            regime={"trend": 1, "volatility_regime": 2, "range_flag": 0},
            sessions={"london": 1},
        )
        results = ms.select_models_by_regime(SYMBOL)
        expected = {"trend_bull", "trend_bear", "high_vol", "low_vol", "ranging", "trending"}
        assert set(results.keys()) == expected

    def test_missing_regime_yields_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        results = ms.select_models_by_regime(SYMBOL)
        for v in results.values():
            assert v["model"] == "unknown"
            assert v["score"] == 0


# -------------------- get_primary_session --------------------

class TestGetPrimarySession:
    def test_returns_none_when_no_active_sessions(self, monkeypatch):
        monkeypatch.setattr(
            "src.features.session.get_current_session_info",
            lambda symbol=None: {"active_sessions": [], "weights": {}},
        )
        assert ms.get_primary_session("EURUSD") is None

    def test_single_active_session_returned_directly(self, monkeypatch):
        monkeypatch.setattr(
            "src.features.session.get_current_session_info",
            lambda symbol=None: {"active_sessions": ["london"], "weights": {"london": 1.0}},
        )
        assert ms.get_primary_session("EURUSD") == "london"

    def test_multiple_sessions_picks_highest_weight(self, monkeypatch):
        monkeypatch.setattr(
            "src.features.session.get_current_session_info",
            lambda symbol=None: {
                "active_sessions": ["london", "new_york"],
                "weights": {"london": 0.3, "new_york": 0.7},
            },
        )
        assert ms.get_primary_session("EURUSD") == "new_york"
