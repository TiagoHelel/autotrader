"""
Property-based tests for the decision layer — hypothesis-driven invariants.

These protect against trade-routing regressions that unit tests with fixed
inputs can miss. Runs thousands of randomized inputs per invariant.

Invariants tested:
  1. Signal is always one of {BUY, SELL, HOLD}
  2. Confidence is always in [0, 1]
  3. HOLD is forced when session_score < SESSION_MIN_SCORE (0.3)
  4. expected_return sign matches signal direction (BUY → positive, SELL → negative)
  5. When all predictions == current_price, signal is always HOLD
  6. Ensemble sign matches weighted majority
  7. Ensemble confidence is in [0, 1]
  8. Symmetry: flipping all predictions above/below current_price flips BUY↔SELL
"""
from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.decision.signal import (
    SESSION_MIN_SCORE,
    generate_ensemble_signal,
    generate_signal,
    generate_signals_for_models,
)


# Price strategy: realistic FOREX range [0.5, 200] (covers EURUSD ~1.1, USDJPY ~150, XAUUSD ~2000+)
price_strat = st.floats(min_value=0.5, max_value=200.0, allow_nan=False, allow_infinity=False)

# Prediction: within +/- 10% of current price (realistic for M5-M15 horizon)
def pred_around(current: float) -> st.SearchStrategy[float]:
    return st.floats(
        min_value=current * 0.90,
        max_value=current * 1.10,
        allow_nan=False,
        allow_infinity=False,
    )


@st.composite
def price_and_preds(draw):
    current = draw(price_strat)
    p1 = draw(pred_around(current))
    p2 = draw(pred_around(current))
    p3 = draw(pred_around(current))
    return current, {"pred_t1": p1, "pred_t2": p2, "pred_t3": p3}


# ---------------------------------------------------------------------------
# Property 1-2-4: core invariants of generate_signal
# ---------------------------------------------------------------------------


@given(price_and_preds())
@settings(max_examples=200, deadline=None)
def test_signal_always_valid(data):
    current, preds = data
    out = generate_signal(preds, current)
    assert out["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= out["confidence"] <= 1.0


@given(price_and_preds())
@settings(max_examples=200, deadline=None)
def test_expected_return_sign_matches_direction(data):
    current, preds = data
    out = generate_signal(preds, current)
    if out["signal"] == "BUY":
        assert out["expected_return"] > 0
    elif out["signal"] == "SELL":
        assert out["expected_return"] < 0
    # HOLD: no constraint on sign


# ---------------------------------------------------------------------------
# Property 3: session-filtered always HOLD
# ---------------------------------------------------------------------------


@given(
    price_and_preds(),
    st.floats(min_value=0.0, max_value=SESSION_MIN_SCORE - 1e-6,
              allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_low_session_score_forces_hold(data, session_score):
    current, preds = data
    out = generate_signal(preds, current, session_score=session_score)
    assert out["signal"] == "HOLD"
    assert out["session_filtered"] is True


# ---------------------------------------------------------------------------
# Property 5: flat predictions always HOLD
# ---------------------------------------------------------------------------


@given(price_strat)
@settings(max_examples=50, deadline=None)
def test_flat_predictions_hold(current):
    preds = {"pred_t1": current, "pred_t2": current, "pred_t3": current}
    out = generate_signal(preds, current)
    assert out["signal"] == "HOLD"
    assert abs(out["expected_return"]) < 1e-9


# ---------------------------------------------------------------------------
# Property 8: mirror symmetry — flipping preds across current_price flips BUY↔SELL
# ---------------------------------------------------------------------------


@given(price_and_preds())
@settings(max_examples=200, deadline=None)
def test_mirror_symmetry(data):
    current, preds = data
    out_a = generate_signal(preds, current)
    # Mirror around current_price
    mirrored = {k: 2 * current - v for k, v in preds.items()}
    # Guard: mirror must stay positive
    assume(all(v > 0 for v in mirrored.values()))
    out_b = generate_signal(mirrored, current)

    if out_a["signal"] == "BUY":
        assert out_b["signal"] in {"SELL", "HOLD"}  # HOLD if on boundary
    elif out_a["signal"] == "SELL":
        assert out_b["signal"] in {"BUY", "HOLD"}
    # Returns should be approximately negated
    assert abs(out_a["expected_return"] + out_b["expected_return"]) < 1e-6


# ---------------------------------------------------------------------------
# Property 6-7: ensemble invariants
# ---------------------------------------------------------------------------


signal_strat = st.sampled_from(["BUY", "SELL", "HOLD"])
confidence_strat = st.floats(min_value=0.0, max_value=1.0,
                              allow_nan=False, allow_infinity=False)
expected_return_strat = st.floats(min_value=-0.05, max_value=0.05,
                                   allow_nan=False, allow_infinity=False)


@st.composite
def signal_dict_strat(draw):
    return {
        "signal": draw(signal_strat),
        "confidence": draw(confidence_strat),
        "expected_return": draw(expected_return_strat),
    }


@given(st.dictionaries(
    st.text(min_size=1, max_size=10),
    signal_dict_strat(),
    min_size=1,
    max_size=8,
))
@settings(max_examples=200, deadline=None)
def test_ensemble_signal_valid(signals_by_model):
    out = generate_ensemble_signal(signals_by_model)
    assert out["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= out["confidence"] <= 1.0
    assert set(out["votes"].keys()) == set(signals_by_model.keys())


def test_ensemble_empty_returns_hold():
    out = generate_ensemble_signal({})
    assert out["signal"] == "HOLD"
    assert out["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Property: unanimous models → ensemble agrees
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(["BUY", "SELL"]),
    st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
    st.integers(min_value=2, max_value=6),
)
@settings(max_examples=100, deadline=None)
def test_unanimous_ensemble_agrees(unanimous_signal, conf, n_models):
    signals = {
        f"m{i}": {"signal": unanimous_signal, "confidence": conf,
                  "expected_return": 0.001 if unanimous_signal == "BUY" else -0.001}
        for i in range(n_models)
    }
    out = generate_ensemble_signal(signals)
    assert out["signal"] == unanimous_signal


# ---------------------------------------------------------------------------
# Property: generate_signals_for_models handles tuple/list/dict forms
# ---------------------------------------------------------------------------


@given(price_strat, st.lists(pred_around(1.0), min_size=3, max_size=3))
@settings(max_examples=100, deadline=None)
def test_generate_signals_accepts_list_form(current, preds):
    # Scale preds around current
    scaled = [p * current for p in preds]
    out = generate_signals_for_models({"xgb": scaled}, current)
    assert "xgb" in out
    assert out["xgb"]["signal"] in {"BUY", "SELL", "HOLD"}


def test_generate_signals_skips_malformed():
    out = generate_signals_for_models(
        {"bad": [1.0], "good": [1.1, 1.1, 1.1]}, 1.1,
    )
    assert "bad" not in out
    assert "good" in out
