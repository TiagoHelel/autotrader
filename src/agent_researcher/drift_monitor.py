"""Monitor active strategies against daily_eval outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.agent_researcher.paths import PROJECT_ROOT
from src.agent_researcher.state_manager import StateManager
from src.agent_researcher.strategy_manager import StrategyManager


DEGRADING_DROP_PP = 0.10
DEGRADING_FLOOR = 0.50
DEAD_FLOOR = 0.45


class DriftMonitor:
    """Detect hit-rate degradation for active strategies."""

    def __init__(
        self,
        strategy_manager: StrategyManager,
        state_manager: StateManager,
        eval_path: Path | None = None,
    ) -> None:
        self.strategy_manager = strategy_manager
        self.state_manager = state_manager
        self.eval_path = eval_path

    def check(self) -> list[dict[str, Any]]:
        """Check every active strategy and update/reject when needed."""
        eval_df = self._load_eval()
        if eval_df.empty:
            return []
        events: list[dict[str, Any]] = []
        for strategy in self.strategy_manager.load_active():
            event = self._check_strategy(strategy, eval_df)
            if event:
                events.append(event)
        return events

    def _check_strategy(
        self,
        strategy: dict[str, Any],
        eval_df: pd.DataFrame,
    ) -> dict[str, Any] | None:
        filtered = apply_daily_eval_filters(eval_df, strategy.get("filters", {}))
        if filtered.empty or "hit_t1" not in filtered.columns:
            return None
        traded = filtered
        if "signal" in traded.columns:
            traded = traded[traded["signal"].isin(["BUY", "SELL"])]
        if len(traded) < 30:
            status = "healthy"
            current_hit = None
        else:
            current_hit = float(traded["hit_t1"].mean())
            baseline = float(strategy.get("metrics", {}).get("win_rate", 0.0))
            drop = baseline - current_hit
            previous = self.state_manager.previous_drift_status(strategy["id"])
            if current_hit < DEAD_FLOOR or (
                previous == "degrading" and current_hit < DEGRADING_FLOOR
            ):
                status = "dead"
            elif drop > DEGRADING_DROP_PP or current_hit < DEGRADING_FLOOR:
                status = "degrading"
            else:
                status = "healthy"

        self.state_manager.record_drift_status(strategy["id"], status)
        if status == "dead":
            self.strategy_manager.reject_strategy(
                strategy,
                reason="performance drift marked strategy dead",
            )
        else:
            self.strategy_manager.update_decay_status(strategy, status)
        return {
            "strategy_id": strategy["id"],
            "status": status,
            "current_hit_rate": current_hit,
            "n": int(len(traded)),
        }

    def _load_eval(self) -> pd.DataFrame:
        path = self.eval_path or latest_eval_path()
        if path is None or not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()


def latest_eval_path() -> Path | None:
    """Return latest daily_eval output by file name."""
    research_dir = PROJECT_ROOT / "data" / "research"
    if not research_dir.exists():
        return None
    candidates = sorted(research_dir.glob("eval_*.parquet"), reverse=True)
    return candidates[0] if candidates else None


def apply_daily_eval_filters(
    df: pd.DataFrame,
    filters: dict[str, Any],
) -> pd.DataFrame:
    """Apply conditional_analysis-like filters to daily_eval schema."""
    out = df
    key_map = {
        "trend": "regime_trend",
        "volatility_regime": "regime_vol",
        "range_flag": "regime_range",
    }
    for key, value in filters.items():
        column = key_map.get(key, key)
        if out.empty:
            return out
        if key == "confidence_min" and "confidence" in out.columns:
            out = out[out["confidence"].astype(float) >= float(value)]
        elif key == "hour_utc" and "timestamp" in out.columns:
            timestamps = pd.to_datetime(out["timestamp"], errors="coerce")
            lo, hi = value
            out = out[(timestamps.dt.hour >= lo) & (timestamps.dt.hour < hi)]
        elif key in {"confidence", "session_score"} and column in out.columns:
            lo, hi = value
            out = out[
                (out[column].astype(float) >= float(lo))
                & (out[column].astype(float) <= float(hi))
            ]
        elif column in out.columns:
            if isinstance(value, (list, tuple, set)):
                out = out[out[column].isin(list(value))]
            else:
                out = out[out[column] == value]
    return out
