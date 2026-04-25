"""Persistent state for statistical safety and reproducibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.agent_researcher.models import utc_now_iso
from src.agent_researcher.paths import STATE_PATH, assert_agent_write_path


def normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Normalize filters so semantically equal filters hash the same way."""
    normalized: dict[str, Any] = {}
    for key, value in sorted(filters.items()):
        if isinstance(value, tuple):
            normalized[key] = list(value)
        elif isinstance(value, list):
            normalized[key] = value
        elif isinstance(value, dict):
            normalized[key] = normalize_filters(value)
        else:
            normalized[key] = value
    return normalized


def hash_filters(filters: dict[str, Any]) -> str:
    """Stable hash compatible with the conditional analysis convention."""
    payload = json.dumps(normalize_filters(filters), sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


class StateManager:
    """Read and write the agent-owned state JSON file."""

    def __init__(self, path: Path = STATE_PATH, enforce_boundary: bool = True) -> None:
        self.path = assert_agent_write_path(path) if enforce_boundary else path
        self.state = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "tested_filter_hashes": {},
                "used_holdouts": {},
                "active_strategy_ids": [],
                "last_run_at": None,
                "drift_history": {},
            }
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self) -> None:
        """Persist state atomically enough for a single local process."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(self.path)

    def mark_run(self) -> None:
        """Record a successful orchestrator run timestamp."""
        self.state["last_run_at"] = utc_now_iso()
        self.save()

    def has_tested_filter(self, filter_hash: str) -> bool:
        """Return True if a filter was already tested by this agent."""
        return filter_hash in self.state["tested_filter_hashes"]

    def mark_filter_tested(
        self,
        filter_hash: str,
        filters: dict[str, Any],
        verdict: str,
    ) -> None:
        """Record that a filter has consumed one research test."""
        self.state["tested_filter_hashes"][filter_hash] = {
            "filters": normalize_filters(filters),
            "verdict": verdict,
            "timestamp": utc_now_iso(),
        }
        self.save()

    def has_used_holdout(self, filter_hash: str) -> bool:
        """Return True if a filter already consumed its one holdout use."""
        return filter_hash in self.state["used_holdouts"]

    def mark_holdout_used(
        self,
        filter_hash: str,
        filters: dict[str, Any],
        verdict: str,
    ) -> None:
        """Record holdout usage even if the holdout verdict rejects the idea."""
        self.state["used_holdouts"][filter_hash] = {
            "filters": normalize_filters(filters),
            "verdict": verdict,
            "timestamp": utc_now_iso(),
        }
        self.save()

    def add_active_strategy(self, strategy_id: str) -> None:
        """Track an active strategy id."""
        ids = self.state.setdefault("active_strategy_ids", [])
        if strategy_id not in ids:
            ids.append(strategy_id)
            self.save()

    def remove_active_strategy(self, strategy_id: str) -> None:
        """Remove a strategy id from active tracking."""
        ids = self.state.setdefault("active_strategy_ids", [])
        if strategy_id in ids:
            ids.remove(strategy_id)
            self.save()

    def record_drift_status(self, strategy_id: str, status: str) -> None:
        """Append a drift status to the strategy history."""
        history = self.state.setdefault("drift_history", {})
        entries = history.setdefault(strategy_id, [])
        entries.append({"status": status, "timestamp": utc_now_iso()})
        self.save()

    def previous_drift_status(self, strategy_id: str) -> str | None:
        """Return the latest drift status seen before the current check."""
        entries = self.state.get("drift_history", {}).get(strategy_id, [])
        if not entries:
            return None
        return str(entries[-1].get("status"))
