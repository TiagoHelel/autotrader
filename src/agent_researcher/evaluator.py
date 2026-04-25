"""Evaluation wrapper around src.research.conditional_analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from src.agent_researcher.models import EvaluationRecord, Hypothesis, ResultSummary
from src.agent_researcher.paths import PROJECT_ROOT
from src.agent_researcher.state_manager import StateManager, hash_filters
from src.research.conditional_analysis import (
    build_prediction_dataset,
    evaluate_filter,
    split_holdout,
)


PROMISING_VERDICTS = {"PROMISING", "STRONG"}
MIN_TRADES = 30


class EvaluationError(RuntimeError):
    """Raised when no valid research dataset is available."""


class Evaluator:
    """Evaluate hypotheses with research split and one-time holdout usage."""

    def __init__(
        self,
        state_manager: StateManager,
        dataset_path: Path | None = None,
        symbols: Iterable[str] | None = None,
        model: str = "xgboost",
        holdout_pct: float = 0.20,
    ) -> None:
        self.state_manager = state_manager
        self.dataset_path = dataset_path
        self.symbols = list(symbols) if symbols else None
        self.model = model
        self.holdout_pct = holdout_pct
        self._dataset: pd.DataFrame | None = None

    def evaluate(self, hypothesis: Hypothesis) -> EvaluationRecord:
        """Evaluate one hypothesis and consume holdout only when justified."""
        filter_hash = hash_filters(hypothesis.filters)
        record = EvaluationRecord(hypothesis=hypothesis, filter_hash=filter_hash)
        if self.state_manager.has_tested_filter(filter_hash):
            record.status = "skipped"
            record.verdict = "DUPLICATE_FILTER"
            record.insight = "Skipped because this filter hash was already tested."
            return record

        research_df, holdout_df = split_holdout(
            self._load_dataset(),
            holdout_pct=self.holdout_pct,
        )
        research_result = evaluate_filter(
            research_df,
            filters=hypothesis.filters,
            hypothesis=hypothesis.hypothesis,
            holdout=False,
            log=False,
        )
        record.research = ResultSummary.from_filter_result(research_result)
        self.state_manager.mark_filter_tested(
            filter_hash,
            hypothesis.filters,
            record.research.verdict,
        )

        if not _can_try_holdout(record.research):
            record.status = "rejected"
            record.verdict = record.research.verdict
            record.insight = build_insight(record)
            return record

        if self.state_manager.has_used_holdout(filter_hash):
            record.status = "rejected"
            record.verdict = "HOLDOUT_ALREADY_USED"
            record.insight = build_insight(record)
            return record

        holdout_result = evaluate_filter(
            holdout_df,
            filters=hypothesis.filters,
            hypothesis=f"holdout validation: {hypothesis.hypothesis}",
            holdout=False,
            log=False,
        )
        record.holdout = ResultSummary.from_filter_result(holdout_result)
        self.state_manager.mark_holdout_used(
            filter_hash,
            hypothesis.filters,
            record.holdout.verdict,
        )

        if _is_validated(record.holdout):
            record.status = "validated"
            record.verdict = record.holdout.verdict
        else:
            record.status = "rejected"
            record.verdict = record.holdout.verdict
        record.insight = build_insight(record)
        return record

    def _load_dataset(self) -> pd.DataFrame:
        if self._dataset is not None:
            return self._dataset
        if self.dataset_path:
            df = pd.read_parquet(self.dataset_path)
        else:
            df = self._load_latest_prediction_dataset()
        if df.empty:
            raise EvaluationError("research dataset is empty")
        self._dataset = df
        return df

    def _load_latest_prediction_dataset(self) -> pd.DataFrame:
        research_dir = PROJECT_ROOT / "data" / "research"
        candidates = sorted(research_dir.glob("predictions_*.parquet"), reverse=True)
        if candidates:
            return pd.read_parquet(candidates[0])
        if not self.symbols:
            from src.mt5.symbols import DESIRED_SYMBOLS

            self.symbols = list(DESIRED_SYMBOLS)
        return build_prediction_dataset(
            symbols=self.symbols,
            model=self.model,
            save=False,
        )


def _can_try_holdout(result: ResultSummary) -> bool:
    return (
        result.verdict in PROMISING_VERDICTS
        and result.n_trades >= MIN_TRADES
        and result.mean_pnl_net_pips > 0
    )


def _is_validated(result: ResultSummary) -> bool:
    return _can_try_holdout(result)


def build_insight(record: EvaluationRecord) -> str:
    """Create a short, reusable learning statement."""
    research = record.research
    holdout = record.holdout
    if research is None:
        return "No research result was produced."
    if holdout is None:
        return (
            f"Research verdict {research.verdict} with n={research.n_trades}; "
            "holdout was not consumed because the research gate did not pass."
        )
    return (
        f"Research {research.verdict} WR={research.win_rate:.3f}, "
        f"holdout {holdout.verdict} WR={holdout.win_rate:.3f}. "
        f"Final status: {record.status}."
    )
