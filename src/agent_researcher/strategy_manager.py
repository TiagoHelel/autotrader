"""Persist, update, and reject validated strategies."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from src.agent_researcher.models import EvaluationRecord, utc_now_iso
from src.agent_researcher.paths import (
    ACTIVE_STRATEGIES_DIR,
    REJECTED_STRATEGIES_DIR,
    assert_agent_write_path,
)
from src.agent_researcher.state_manager import StateManager


class StrategyManager:
    """Manage strategy JSON files under src/agent_researcher/strategies."""

    def __init__(
        self,
        state_manager: StateManager,
        active_dir: Path = ACTIVE_STRATEGIES_DIR,
        rejected_dir: Path = REJECTED_STRATEGIES_DIR,
        enforce_boundary: bool = True,
    ) -> None:
        self.state_manager = state_manager
        self.active_dir = active_dir
        self.rejected_dir = rejected_dir
        self.enforce_boundary = enforce_boundary

    def persist_validated(self, record: EvaluationRecord) -> dict:
        """Persist a strategy only after holdout validation passes."""
        if record.status != "validated" or record.holdout is None:
            raise ValueError("only validated records can become strategies")
        strategy_id = str(uuid4())
        strategy = {
            "id": strategy_id,
            "created_at": utc_now_iso(),
            "filters": record.hypothesis.filters,
            "hypothesis": record.hypothesis.hypothesis,
            "metrics": {
                "win_rate": record.holdout.win_rate,
                "sharpe": record.holdout.sharpe,
                "p_value": record.holdout.p_value,
            },
            "validation": {
                "holdout_passed": True,
                "timestamp": utc_now_iso(),
                "filter_hash": record.filter_hash,
            },
            "status": "active",
            "decay_monitor": {
                "last_checked": None,
                "current_status": "healthy",
            },
        }
        self._write_strategy(self.active_dir / f"{strategy_id}.json", strategy)
        self.state_manager.add_active_strategy(strategy_id)
        return strategy

    def load_active(self) -> list[dict]:
        """Load active strategy JSON files."""
        if not self.active_dir.exists():
            return []
        strategies = []
        for path in sorted(self.active_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                strategies.append(json.load(handle))
        return strategies

    def update_decay_status(self, strategy: dict, status: str) -> None:
        """Update decay monitor status in place."""
        strategy["decay_monitor"] = {
            "last_checked": utc_now_iso(),
            "current_status": status,
        }
        self._write_strategy(
            self.active_dir / f"{strategy['id']}.json",
            strategy,
        )

    def reject_strategy(self, strategy: dict, reason: str) -> Path:
        """Move an active strategy to rejected/ with a rejection reason."""
        strategy["status"] = "rejected"
        strategy["rejected_at"] = utc_now_iso()
        strategy["rejection_reason"] = reason
        source = self._resolve_path(self.active_dir / f"{strategy['id']}.json")
        target = self._resolve_path(self.rejected_dir / source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._write_strategy(source, strategy)
        shutil.move(str(source), str(target))
        self.state_manager.remove_active_strategy(strategy["id"])
        return target

    def _write_strategy(self, path: Path, strategy: dict) -> None:
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w", encoding="utf-8") as handle:
            json.dump(strategy, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def _resolve_path(self, path: Path) -> Path:
        if self.enforce_boundary:
            return assert_agent_write_path(path)
        return path
