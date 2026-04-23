"""
Tests for src/backtest/engine.py — simulacao de PnL.

Trava o contrato do backtest: spread aplicado corretamente, PnL direcional
correto (BUY = exit - entry, SELL = entry - exit), metricas financeiras
(Sharpe, profit factor, drawdown, winrate), persistencia em parquet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.backtest.engine import (
    DEFAULT_SPREADS,
    run_backtest,
    run_backtest_by_model,
    get_backtest_results,
    get_backtest_summary,
    _compute_metrics,
    _empty_result,
)
from src.mt5.symbols import get_pip_value


# -------------------- Helpers --------------------

def _linear_prices(n=50, start=1.1000, step=0.0001, start_ts="2025-01-02 00:00:00", freq="5min"):
    """Precos crescentes monotonicos — trade BUY deve lucrar sempre."""
    times = pd.date_range(start_ts, periods=n, freq=freq)
    closes = start + np.arange(n) * step
    return pd.DataFrame({
        "time": times,
        "open": closes - step / 2,
        "high": closes + step,
        "low": closes - step,
        "close": closes,
    })


def _predictions(timestamp, current_price, pred_t1, pred_t2=None, pred_t3=None, model="xgboost"):
    return pd.DataFrame([{
        "timestamp": pd.Timestamp(timestamp),
        "model": model,
        "current_price": current_price,
        "pred_t1": pred_t1,
        "pred_t2": pred_t2 if pred_t2 is not None else pred_t1,
        "pred_t3": pred_t3 if pred_t3 is not None else pred_t1,
    }])


# -------------------- run_backtest --------------------

class TestRunBacktest:
    def test_empty_predictions_returns_empty_result(self):
        price_df = _linear_prices()
        pred_df = pd.DataFrame(columns=["timestamp", "model", "current_price", "pred_t1", "pred_t2", "pred_t3"])
        result = run_backtest(pred_df, price_df, symbol="EURUSD")
        assert result["trades_count"] == 0
        assert result["trades"] == []

    def test_prediction_under_threshold_is_skipped(self):
        price_df = _linear_prices()
        # pred_t1 apenas 0.5 pip acima — menor que threshold (3 pips)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.10005, pred_t2=1.10005, pred_t3=1.10005,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD")
        assert result["trades_count"] == 0

    def test_buy_signal_on_rising_prices_is_profitable(self):
        price_df = _linear_prices(n=50, start=1.1000, step=0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD", exit_horizon=3)
        assert result["trades_count"] == 1
        t = result["trades"][0]
        assert t["direction"] == "BUY"
        assert t["pnl_pips"] > 0  # precos subiram → lucro

    def test_sell_signal_on_falling_prices_is_profitable(self):
        price_df = _linear_prices(n=50, start=1.1100, step=-0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1100,
            pred_t1=1.1080, pred_t2=1.1070, pred_t3=1.1060,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD", exit_horizon=3)
        assert result["trades_count"] == 1
        t = result["trades"][0]
        assert t["direction"] == "SELL"
        assert t["pnl_pips"] > 0  # precos cairam → SELL lucra

    def test_spread_reduces_pnl(self):
        """Com spread maior, mesma trade deve ter PnL menor."""
        price_df = _linear_prices(n=50, step=0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        r1 = run_backtest(pred_df, price_df, symbol="EURUSD", spread_pips=0.5)
        r2 = run_backtest(pred_df, price_df, symbol="EURUSD", spread_pips=5.0)
        assert r1["trades"][0]["pnl_pips"] > r2["trades"][0]["pnl_pips"]

    def test_skips_when_not_enough_future_candles(self):
        """Se nao ha exit_horizon+1 candles futuros, skip."""
        # precos so cobrem 2 candles — exit_horizon=3 precisa de >=4
        price_df = _linear_prices(n=2)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD", exit_horizon=3)
        assert result["trades_count"] == 0

    def test_uses_default_spread_when_not_provided(self):
        price_df = _linear_prices(n=50, step=0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD")
        # spread EURUSD default = 1.2 pips
        expected_spread = DEFAULT_SPREADS["EURUSD"] * get_pip_value("EURUSD")
        assert result["trades"][0]["spread_cost"] == pytest.approx(expected_spread)

    def test_result_has_metrics(self):
        price_df = _linear_prices(n=50, step=0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD")
        assert "metrics" in result
        assert "pnl_total" in result["metrics"]
        assert "winrate" in result["metrics"]
        assert "sharpe" in result["metrics"]
        assert "equity_curve" in result["metrics"]

    def test_trade_schema_is_complete(self):
        price_df = _linear_prices(n=50, step=0.0002)
        pred_df = _predictions(
            "2025-01-02 00:00:00",
            current_price=1.1000,
            pred_t1=1.1020, pred_t2=1.1030, pred_t3=1.1040,
        )
        result = run_backtest(pred_df, price_df, symbol="EURUSD")
        t = result["trades"][0]
        expected_keys = {
            "timestamp", "model", "symbol", "direction",
            "entry_price", "exit_price", "entry_time", "exit_time",
            "pnl_price", "pnl_pips", "spread_cost", "expected_return", "exit_horizon",
        }
        assert set(t.keys()) == expected_keys


# -------------------- _compute_metrics --------------------

class TestComputeMetrics:
    @pytest.fixture
    def profitable_trades(self):
        return pd.DataFrame([
            {"pnl_pips": 10.0, "pnl_price": 0.0010, "entry_price": 1.1000},
            {"pnl_pips": 20.0, "pnl_price": 0.0020, "entry_price": 1.1010},
            {"pnl_pips": -5.0, "pnl_price": -0.0005, "entry_price": 1.1020},
            {"pnl_pips": 15.0, "pnl_price": 0.0015, "entry_price": 1.1030},
        ])

    def test_winrate(self, profitable_trades):
        m = _compute_metrics(profitable_trades)
        # 3 winners em 4 → 75%
        assert m["winrate"] == pytest.approx(75.0)
        assert m["winning_trades"] == 3
        assert m["losing_trades"] == 1

    def test_pnl_total_is_sum(self, profitable_trades):
        m = _compute_metrics(profitable_trades)
        # 10 + 20 - 5 + 15 = 40
        assert m["pnl_total"] == pytest.approx(40.0)

    def test_profit_factor(self, profitable_trades):
        m = _compute_metrics(profitable_trades)
        # gross_profit = 10+20+15 = 45, gross_loss = 5, PF = 9.0
        assert m["profit_factor"] == pytest.approx(9.0)

    def test_max_drawdown_non_positive(self, profitable_trades):
        m = _compute_metrics(profitable_trades)
        assert m["max_drawdown"] <= 0

    def test_equity_curve_matches_cumulative(self, profitable_trades):
        m = _compute_metrics(profitable_trades)
        expected = np.cumsum(profitable_trades["pnl_pips"].values).tolist()
        assert m["equity_curve"] == pytest.approx(expected)

    def test_all_losers_has_zero_profit_factor(self):
        df = pd.DataFrame([
            {"pnl_pips": -10.0, "pnl_price": -0.001, "entry_price": 1.1000},
            {"pnl_pips": -5.0, "pnl_price": -0.0005, "entry_price": 1.1010},
        ])
        m = _compute_metrics(df)
        assert m["profit_factor"] == 0
        assert m["winrate"] == 0

    def test_all_winners_has_inf_profit_factor(self):
        df = pd.DataFrame([
            {"pnl_pips": 10.0, "pnl_price": 0.001, "entry_price": 1.1000},
            {"pnl_pips": 20.0, "pnl_price": 0.002, "entry_price": 1.1010},
        ])
        m = _compute_metrics(df)
        assert m["profit_factor"] == float("inf")

    def test_sharpe_is_zero_for_single_trade(self):
        df = pd.DataFrame([
            {"pnl_pips": 10.0, "pnl_price": 0.001, "entry_price": 1.1000},
        ])
        m = _compute_metrics(df)
        # len(returns) <= 1 → sharpe=0
        assert m["sharpe"] == 0.0


# -------------------- _empty_result --------------------

class TestEmptyResult:
    def test_schema(self):
        r = _empty_result("EURUSD")
        assert r["symbol"] == "EURUSD"
        assert r["trades"] == []
        assert r["trades_count"] == 0
        assert r["metrics"]["pnl_total"] == 0
        assert r["metrics"]["equity_curve"] == []


# -------------------- run_backtest_by_model --------------------

@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """Redireciona settings.project_root para tmp_path com raw + predictions."""
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "predictions").mkdir(parents=True)
    monkeypatch.setattr(settings, "project_root", tmp_path)
    return tmp_path


class TestRunBacktestByModel:
    def test_returns_empty_when_files_missing(self, fake_data_dir):
        out = run_backtest_by_model("EURUSD")
        assert out == {}

    def test_runs_per_model_and_persists(self, fake_data_dir):
        # Price data: 50 candles rising
        price_df = _linear_prices(n=50, step=0.0002)
        price_df.to_parquet(fake_data_dir / "data" / "raw" / "EURUSD.parquet")

        # Predictions: 2 modelos, 1 previsao forte cada
        pred_rows = []
        for model in ("xgboost", "linear"):
            pred_rows.append({
                "timestamp": pd.Timestamp("2025-01-02 00:00:00"),
                "model": model,
                "current_price": 1.1000,
                "pred_t1": 1.1020, "pred_t2": 1.1030, "pred_t3": 1.1040,
            })
        pd.DataFrame(pred_rows).to_parquet(
            fake_data_dir / "data" / "predictions" / "EURUSD.parquet"
        )

        out = run_backtest_by_model("EURUSD")
        assert set(out.keys()) == {"xgboost", "linear"}
        for model, result in out.items():
            assert result["trades_count"] == 1
            assert result["model"] == model

        # Persistencia: parquet de trades e de metrics
        bt_dir = fake_data_dir / "data" / "backtest"
        assert (bt_dir / "EURUSD_xgboost.parquet").exists()
        assert (bt_dir / "EURUSD_xgboost_metrics.parquet").exists()


# -------------------- get_backtest_results / summary --------------------

class TestGetBacktestResults:
    def test_returns_empty_dataframe_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        df = get_backtest_results()
        assert df.empty

    def test_filter_by_symbol_and_model(self, fake_data_dir):
        bt_dir = fake_data_dir / "data" / "backtest"
        bt_dir.mkdir(parents=True, exist_ok=True)
        # 2 arquivos de trades
        pd.DataFrame([
            {"model": "xgboost", "pnl_pips": 10.0},
            {"model": "xgboost", "pnl_pips": -5.0},
        ]).to_parquet(bt_dir / "EURUSD_xgboost.parquet")
        pd.DataFrame([
            {"model": "linear", "pnl_pips": 3.0},
        ]).to_parquet(bt_dir / "EURUSD_linear.parquet")

        all_df = get_backtest_results("EURUSD")
        assert len(all_df) == 3
        only_xgb = get_backtest_results("EURUSD", "xgboost")
        assert len(only_xgb) == 2
        assert set(only_xgb["model"].unique()) == {"xgboost"}


class TestGetBacktestSummary:
    def test_empty_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "project_root", tmp_path)
        assert get_backtest_summary() == []

    def test_sorted_by_pnl_total_desc(self, fake_data_dir):
        bt_dir = fake_data_dir / "data" / "backtest"
        bt_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"symbol": "EURUSD", "model": "xgb", "pnl_total": 50.0}]).to_parquet(
            bt_dir / "EURUSD_xgb_metrics.parquet"
        )
        pd.DataFrame([{"symbol": "GBPUSD", "model": "rf", "pnl_total": 120.0}]).to_parquet(
            bt_dir / "GBPUSD_rf_metrics.parquet"
        )
        pd.DataFrame([{"symbol": "USDJPY", "model": "linear", "pnl_total": -10.0}]).to_parquet(
            bt_dir / "USDJPY_linear_metrics.parquet"
        )

        summary = get_backtest_summary()
        pnls = [s["pnl_total"] for s in summary]
        assert pnls == sorted(pnls, reverse=True)
        assert summary[0]["pnl_total"] == 120.0
