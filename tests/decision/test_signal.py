"""
Tests for src/decision/signal.py — geracao de sinais BUY/SELL/HOLD.

Trava o contrato do core da decision layer:
- session_score < 0.3 forca HOLD
- expected_return > threshold + confidence >= min → BUY (espelhado p/ SELL)
- confidence = 0.6 * agreement_entre_horizontes + 0.4 * magnitude
- ensemble = votacao ponderada por confianca (empate → HOLD)
"""

from __future__ import annotations

import pytest

from src.decision.signal import (
    DEFAULT_CONFIDENCE_MIN,
    DEFAULT_THRESHOLD,
    generate_signal,
    generate_signals_for_models,
    generate_ensemble_signal,
    log_signal,
)


# -------------------- generate_signal --------------------

class TestGenerateSignal:
    def test_strong_up_move_yields_buy(self):
        preds = {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015}
        r = generate_signal(preds, current_price=1.1000)
        assert r["signal"] == "BUY"
        assert r["expected_return"] > DEFAULT_THRESHOLD
        assert r["confidence"] >= DEFAULT_CONFIDENCE_MIN

    def test_strong_down_move_yields_sell(self):
        preds = {"pred_t1": 1.0995, "pred_t2": 1.0990, "pred_t3": 1.0985}
        r = generate_signal(preds, current_price=1.1000)
        assert r["signal"] == "SELL"
        assert r["expected_return"] < -DEFAULT_THRESHOLD

    def test_flat_preds_yield_hold(self):
        preds = {"pred_t1": 1.1000, "pred_t2": 1.1000, "pred_t3": 1.1000}
        r = generate_signal(preds, current_price=1.1000)
        assert r["signal"] == "HOLD"
        assert r["expected_return"] == 0.0

    def test_move_under_threshold_yields_hold(self):
        # 1 pip up — abaixo do threshold default (3 pips)
        preds = {"pred_t1": 1.10005, "pred_t2": 1.10005, "pred_t3": 1.10005}
        r = generate_signal(preds, current_price=1.1000)
        assert r["signal"] == "HOLD"

    def test_disagreement_lowers_confidence_and_may_hold(self):
        # t1 up, t2 down, t3 up — agreement = |1 - 1 + 1| / 3 = 1/3
        preds = {"pred_t1": 1.1010, "pred_t2": 1.0990, "pred_t3": 1.1020}
        r = generate_signal(preds, current_price=1.1000)
        # confidence baixa pela disagreement; pode sair HOLD
        assert r["confidence"] < 0.8

    def test_session_score_below_min_forces_hold(self):
        preds = {"pred_t1": 1.1020, "pred_t2": 1.1020, "pred_t3": 1.1020}
        r = generate_signal(preds, current_price=1.1000, session_score=0.1)
        assert r["signal"] == "HOLD"
        assert r["session_filtered"] is True

    def test_high_session_lowers_threshold(self):
        """session_score >= 0.6 → threshold * 0.7 (mais agressivo)."""
        r = generate_signal(
            {"pred_t1": 1.1000, "pred_t2": 1.1000, "pred_t3": 1.1000},
            current_price=1.1000,
            session_score=0.9,
        )
        assert r["threshold"] == pytest.approx(DEFAULT_THRESHOLD * 0.7)
        assert r["session_filtered"] is False

    def test_low_session_raises_threshold(self):
        """session_score entre 0.3 e < (na verdade: o codigo tem um branch `else` inatingivel)."""
        # O modulo define 3 multipliers (high/medium/low), mas a logica usa
        # session_score >= 0.6 → high, >= 0.3 → medium, else → low.
        # Como abaixo de 0.3 cai em "session_filtered", testamos apenas high/medium.
        r = generate_signal(
            {"pred_t1": 1.1000, "pred_t2": 1.1000, "pred_t3": 1.1000},
            current_price=1.1000,
            session_score=0.4,
        )
        assert r["threshold"] == pytest.approx(DEFAULT_THRESHOLD * 1.0)

    def test_missing_preds_fall_back_to_current_price(self):
        r = generate_signal({}, current_price=1.1000)
        assert r["signal"] == "HOLD"
        assert r["pred_t1"] == 1.1000
        assert r["pred_t2"] == 1.1000
        assert r["pred_t3"] == 1.1000

    def test_custom_threshold_and_confidence_min(self):
        # Threshold muito alto — sinal forte nao basta
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
            threshold=0.01,  # 100 pips
        )
        assert r["signal"] == "HOLD"
        assert r["threshold"] == 0.01

    def test_zero_current_price_does_not_crash(self):
        r = generate_signal({"pred_t1": 0.1}, current_price=0.0)
        # nao deve dividir por zero
        assert r["expected_return"] == 0.0
        assert r["signal"] == "HOLD"

    def test_result_has_expected_schema(self):
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
        )
        expected_keys = {
            "signal", "confidence", "expected_return",
            "pred_t1", "pred_t2", "pred_t3",
            "current_price", "threshold",
            "session_score", "session_filtered",
            "trajectory_ok", "temporal_conviction",
        }
        assert set(r.keys()) == expected_keys
        assert r["signal"] in {"BUY", "SELL", "HOLD"}
        assert 0.0 <= r["confidence"] <= 1.0

    def test_monotonic_buy_trajectory_is_ok(self):
        """pred_t1 > current, pred_t2 > pred_t1, pred_t3 > pred_t2 → trajectory_ok=True."""
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
        )
        assert r["trajectory_ok"] is True

    def test_monotonic_sell_trajectory_is_ok(self):
        r = generate_signal(
            {"pred_t1": 1.0995, "pred_t2": 1.0990, "pred_t3": 1.0985},
            current_price=1.1000,
        )
        assert r["trajectory_ok"] is True

    def test_non_monotonic_trajectory_is_not_ok(self):
        """pred_t2 dips below pred_t1 → trajectory_ok=False even if direction is positive."""
        r = generate_signal(
            {"pred_t1": 1.1010, "pred_t2": 1.1005, "pred_t3": 1.1020},
            current_price=1.1000,
        )
        assert r["trajectory_ok"] is False

    def test_trajectory_filter_forces_hold_when_not_monotonic(self):
        """trajectory_filter=True + non-monotonic → HOLD, even if expected_return > threshold."""
        r = generate_signal(
            {"pred_t1": 1.1010, "pred_t2": 1.1005, "pred_t3": 1.1020},
            current_price=1.1000,
            trajectory_filter=True,
        )
        assert r["signal"] == "HOLD"
        assert r["trajectory_ok"] is False

    def test_trajectory_filter_does_not_block_monotonic_buy(self):
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
            trajectory_filter=True,
        )
        assert r["signal"] == "BUY"
        assert r["trajectory_ok"] is True

    def test_temporal_conviction_stored_in_result(self):
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
            temporal_conviction="high",
        )
        assert r["temporal_conviction"] == "high"

    def test_temporal_conviction_defaults_to_none(self):
        r = generate_signal(
            {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
            current_price=1.1000,
        )
        assert r["temporal_conviction"] is None


# -------------------- generate_signals_for_models --------------------

class TestGenerateSignalsForModels:
    def test_list_of_preds_converted_to_signal(self):
        preds_by_model = {
            "xgboost": [1.1005, 1.1010, 1.1015],
            "linear": [1.0995, 1.0990, 1.0985],
        }
        out = generate_signals_for_models(preds_by_model, current_price=1.1000)
        assert out["xgboost"]["signal"] == "BUY"
        assert out["linear"]["signal"] == "SELL"

    def test_accepts_dict_preds(self):
        preds_by_model = {
            "xgboost": {"pred_t1": 1.1005, "pred_t2": 1.1010, "pred_t3": 1.1015},
        }
        out = generate_signals_for_models(preds_by_model, current_price=1.1000)
        assert "xgboost" in out
        assert out["xgboost"]["signal"] == "BUY"

    def test_skips_malformed_preds(self):
        preds_by_model = {
            "good": [1.1005, 1.1010, 1.1015],
            "bad_short": [1.1005, 1.1010],          # len < 3 → skip
            "bad_scalar": 1.1005,                    # nao iteravel nem dict → skip
        }
        out = generate_signals_for_models(preds_by_model, current_price=1.1000)
        assert "good" in out
        assert "bad_short" not in out
        assert "bad_scalar" not in out

    def test_session_score_propagates(self):
        preds_by_model = {"xgboost": [1.1020, 1.1020, 1.1020]}
        out = generate_signals_for_models(preds_by_model, current_price=1.1000, session_score=0.1)
        assert out["xgboost"]["signal"] == "HOLD"
        assert out["xgboost"]["session_filtered"] is True


# -------------------- generate_ensemble_signal --------------------

class TestGenerateEnsembleSignal:
    def _buy(self, conf=0.8, er=0.001):
        return {"signal": "BUY", "confidence": conf, "expected_return": er}

    def _sell(self, conf=0.8, er=-0.001):
        return {"signal": "SELL", "confidence": conf, "expected_return": er}

    def _hold(self, conf=0.3, er=0.0):
        return {"signal": "HOLD", "confidence": conf, "expected_return": er}

    def test_empty_dict_returns_hold(self):
        out = generate_ensemble_signal({})
        assert out["signal"] == "HOLD"
        assert out["confidence"] == 0.0
        assert out["votes"] == {}

    def test_majority_buy_wins(self):
        out = generate_ensemble_signal({
            "xgb": self._buy(),
            "rf": self._buy(),
            "linear": self._sell(),
        })
        assert out["signal"] == "BUY"
        assert out["votes"] == {"xgb": "BUY", "rf": "BUY", "linear": "SELL"}

    def test_majority_sell_wins(self):
        out = generate_ensemble_signal({
            "xgb": self._sell(),
            "rf": self._sell(),
            "linear": self._buy(),
        })
        assert out["signal"] == "SELL"

    def test_weights_override_equal_vote(self):
        """1 BUY vs 1 SELL — weight do BUY (3x) vence."""
        out = generate_ensemble_signal(
            {"xgb": self._buy(), "linear": self._sell()},
            weights={"xgb": 3.0, "linear": 1.0},
        )
        assert out["signal"] == "BUY"

    def test_all_hold_yields_hold(self):
        out = generate_ensemble_signal({
            "xgb": self._hold(),
            "rf": self._hold(),
        })
        assert out["signal"] == "HOLD"

    def test_weighted_return_averages_by_weight(self):
        out = generate_ensemble_signal(
            {
                "xgb": self._buy(conf=0.9, er=0.004),
                "linear": self._sell(conf=0.5, er=-0.002),
            },
            weights={"xgb": 1.0, "linear": 1.0},
        )
        # weighted_return = (0.004*1 + -0.002*1) / 2 = 0.001
        assert out["expected_return"] == pytest.approx(0.001, rel=1e-3)

    def test_confidence_within_unit_interval(self):
        out = generate_ensemble_signal({
            "xgb": self._buy(conf=0.95),
            "rf": self._buy(conf=0.90),
        })
        assert 0.0 <= out["confidence"] <= 1.0

    def test_result_schema(self):
        out = generate_ensemble_signal({"xgb": self._buy()})
        assert set(out.keys()) >= {
            "signal", "confidence", "expected_return",
            "votes", "buy_score", "sell_score", "hold_score",
        }


# -------------------- log_signal --------------------

class TestLogSignal:
    def test_log_signal_calls_log_decision(self, monkeypatch):
        captured = {}

        def fake_log_decision(symbol, action, details):
            captured["args"] = (symbol, action, details)

        monkeypatch.setattr("src.decision.signal.log_decision", fake_log_decision)

        sig_data = {"signal": "BUY", "confidence": 0.87, "expected_return": 0.0012}
        log_signal("EURUSD", "xgboost", sig_data)

        assert captured["args"][0] == "EURUSD"
        assert captured["args"][1] == "signal_xgboost"
        assert "signal=BUY" in captured["args"][2]
        assert "conf=0.8700" in captured["args"][2]
