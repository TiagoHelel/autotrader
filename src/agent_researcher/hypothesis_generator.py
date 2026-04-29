"""Prepare context and request new hypotheses from OpenCode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.agent_researcher.hpo_context import load_hpo_summary
from src.agent_researcher.llm_interface import OpenCodeClient
from src.agent_researcher.models import Hypothesis
from src.agent_researcher.paths import ACTIVE_STRATEGIES_DIR, PROJECT_ROOT
from src.agent_researcher.state_manager import StateManager
from src.agent_researcher.vault_reader import VaultReader
from src.features.session import is_market_open


class HypothesisGenerator:
    """LLM-backed hypothesis generator with memory-aware context."""

    def __init__(
        self,
        llm_client: OpenCodeClient,
        vault_reader: VaultReader,
        state_manager: StateManager,
    ) -> None:
        self.llm_client = llm_client
        self.vault_reader = vault_reader
        self.state_manager = state_manager

    def generate(self, max_hypotheses: int = 3) -> list[Hypothesis]:
        """Generate hypotheses while exposing prior failures and live context."""
        context = {
            "vault": self.vault_reader.load_context(),
            "tested_filters": self.state_manager.state.get(
                "tested_filter_hashes",
                {},
            ),
            "used_holdouts": self.state_manager.state.get("used_holdouts", {}),
            "daily_eval": load_daily_eval_summary(),
            "filter_log": load_filter_log_summary(),
            "active_strategies": load_active_strategy_summary(),
            "hpo_summary": load_hpo_summary(),
        }
        return self.llm_client.generate_hypotheses(
            context,
            max_hypotheses=max_hypotheses,
        )


def load_daily_eval_summary(max_files: int = 15) -> list[dict[str, Any]]:
    """Load compact summaries from recent daily_eval parquet outputs."""
    research_dir = PROJECT_ROOT / "data" / "research"
    if not research_dir.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for path in sorted(research_dir.glob("eval_*.parquet"), reverse=True)[:max_files]:
        try:
            df = pd.read_parquet(path)
        except (OSError, ValueError):
            continue
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df[ts.apply(is_market_open)]
        summary: dict[str, Any] = {
            "file": str(path.relative_to(PROJECT_ROOT)),
            "rows": int(len(df)),
        }
        if {"model", "hit_t1"}.issubset(df.columns):
            by_model = df.groupby("model", dropna=False)["hit_t1"].mean()
            summary["hit_t1_by_model"] = {
                str(k): round(float(v), 4) for k, v in by_model.items()
            }
        if {"session", "hit_t1"}.issubset(df.columns):
            by_session = df.groupby("session", dropna=False)["hit_t1"].mean()
            summary["hit_t1_by_session"] = {
                str(k): round(float(v), 4) for k, v in by_session.items()
            }
        for col in ("symbol", "trend", "volatility_regime", "hour_utc"):
            if {col, "hit_t1"}.issubset(df.columns):
                grouped = df.groupby(col, dropna=False)["hit_t1"].agg(
                    ["mean", "count"]
                )
                summary[f"hit_t1_by_{col}"] = {
                    str(k): {
                        "mean": round(float(row["mean"]), 4),
                        "n": int(row["count"]),
                    }
                    for k, row in grouped.iterrows()
                }
        summaries.append(summary)
    return summaries


def load_filter_log_summary(max_rows: int = 200) -> list[dict[str, Any]]:
    """Read the existing filter log as read-only Bonferroni context."""
    path = PROJECT_ROOT / "data" / "research" / "filter_log.parquet"
    if not path.exists():
        return []
    try:
        df = pd.read_parquet(path).tail(max_rows)
    except (OSError, ValueError):
        return []
    columns = [
        col
        for col in (
            "timestamp",
            "filter_hash",
            "filters_json",
            "hypothesis",
            "holdout",
            "verdict",
            "n_trades",
            "win_rate",
            "p_value_vs_coinflip",
        )
        if col in df.columns
    ]
    return df[columns].to_dict(orient="records")


def load_active_strategy_summary(
    directory: Path = ACTIVE_STRATEGIES_DIR,
) -> list[dict[str, Any]]:
    """Read active strategies owned by the agent."""
    if not directory.exists():
        return []
    strategies = []
    for path in sorted(directory.glob("*.json")):
        try:
            strategies.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return strategies
