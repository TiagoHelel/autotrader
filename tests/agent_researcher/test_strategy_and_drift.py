import pandas as pd

from src.agent_researcher.drift_monitor import DriftMonitor
from src.agent_researcher.models import EvaluationRecord, Hypothesis, ResultSummary
from src.agent_researcher.state_manager import StateManager
from src.agent_researcher.strategy_manager import StrategyManager


def _validated_record() -> EvaluationRecord:
    hypothesis = Hypothesis(
        hypothesis="High confidence XAUUSD",
        filters={"symbol": "XAUUSD", "confidence_min": 0.85},
        reasoning="High confidence means model agreement.",
        expected_behavior="Positive hit rate.",
    )
    result = ResultSummary(
        n_trades=80,
        win_rate=0.62,
        sharpe=1.1,
        p_value=0.01,
        verdict="PROMISING",
        mean_pnl_net_pips=1.2,
        max_drawdown_pips=-8.0,
        filter_hash="abc123",
    )
    return EvaluationRecord(
        hypothesis=hypothesis,
        filter_hash="abc123",
        research=result,
        holdout=result,
        status="validated",
        verdict="PROMISING",
    )


def test_strategy_manager_persists_validated_strategy(tmp_path):
    state = StateManager(tmp_path / "agent" / "state.json", enforce_boundary=False)
    manager = StrategyManager(
        state_manager=state,
        active_dir=tmp_path / "agent" / "strategies" / "active",
        rejected_dir=tmp_path / "agent" / "strategies" / "rejected",
        enforce_boundary=False,
    )

    strategy = manager.persist_validated(_validated_record())

    assert strategy["status"] == "active"
    assert len(manager.load_active()) == 1


def test_drift_monitor_rejects_dead_strategy(tmp_path):
    state = StateManager(tmp_path / "agent" / "state.json", enforce_boundary=False)
    manager = StrategyManager(
        state_manager=state,
        active_dir=tmp_path / "agent" / "strategies" / "active",
        rejected_dir=tmp_path / "agent" / "strategies" / "rejected",
        enforce_boundary=False,
    )
    strategy = manager.persist_validated(_validated_record())
    eval_df = pd.DataFrame(
        {
            "symbol": ["XAUUSD"] * 40,
            "confidence": [0.9] * 40,
            "signal": ["BUY"] * 40,
            "hit_t1": [False] * 40,
        }
    )

    monitor = DriftMonitor(
        strategy_manager=manager,
        state_manager=state,
    )
    monitor._load_eval = lambda: eval_df
    events = monitor.check()

    assert events[0]["status"] == "dead"
    assert manager.load_active() == []
    rejected_path = (
        tmp_path / "agent" / "strategies" / "rejected" / f"{strategy['id']}.json"
    )
    assert rejected_path.exists()
