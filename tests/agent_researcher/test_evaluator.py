import pandas as pd

from src.agent_researcher.evaluator import Evaluator
from src.agent_researcher.models import Hypothesis
from src.agent_researcher.state_manager import StateManager, hash_filters


def _dataset() -> pd.DataFrame:
    rows = []
    for index in range(200):
        rows.append(
            {
                "symbol": "XAUUSD",
                "timestamp": pd.Timestamp("2026-01-01")
                + pd.Timedelta(minutes=5 * index),
                "model": "xgboost",
                "hour_utc": 14,
                "session": "new_york",
                "session_score": 0.8,
                "trend": 1,
                "volatility_regime": 1,
                "confidence": 0.9,
                "signal": "BUY",
                "pnl_if_traded_pips": 2.0,
                "pnl_if_traded_net_pips": 1.9,
            }
        )
    return pd.DataFrame(rows)


def test_evaluator_consumes_holdout_once_for_promising_filter(tmp_path):
    state = StateManager(tmp_path / "agent" / "state.json", enforce_boundary=False)
    evaluator = Evaluator(state_manager=state)
    evaluator._dataset = _dataset()
    hypothesis = Hypothesis(
        hypothesis="NY flow edge in XAUUSD",
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15)},
        reasoning="NY liquidity should reinforce directional follow-through.",
        expected_behavior="Win rate above 50% with positive net pnl.",
    )

    record = evaluator.evaluate(hypothesis)

    assert record.status == "validated"
    assert record.holdout is not None
    assert state.has_used_holdout(hash_filters(hypothesis.filters))


def test_evaluator_skips_duplicate_filter(tmp_path):
    state = StateManager(tmp_path / "agent" / "state.json", enforce_boundary=False)
    evaluator = Evaluator(state_manager=state)
    evaluator._dataset = _dataset()
    hypothesis = Hypothesis(
        hypothesis="NY flow edge in XAUUSD",
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15)},
        reasoning="NY liquidity should reinforce directional follow-through.",
        expected_behavior="Win rate above 50% with positive net pnl.",
    )

    evaluator.evaluate(hypothesis)
    duplicate = evaluator.evaluate(hypothesis)

    assert duplicate.status == "skipped"
    assert duplicate.verdict == "DUPLICATE_FILTER"
