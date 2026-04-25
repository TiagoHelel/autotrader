"""Autonomous research loop for LLM-generated conditional strategies."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from src.agent_researcher.drift_monitor import DriftMonitor
from src.agent_researcher.evaluator import EvaluationError, Evaluator
from src.agent_researcher.hypothesis_generator import HypothesisGenerator
from src.agent_researcher.llm_interface import LLMCallError, OpenCodeClient
from src.agent_researcher.paths import ensure_agent_dirs
from src.agent_researcher.state_manager import StateManager, hash_filters
from src.agent_researcher.strategy_manager import StrategyManager
from src.agent_researcher.vault_reader import VaultReader
from src.agent_researcher.vault_writer import VaultWriter


logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """Coordinate context loading, generation, evaluation, and monitoring."""

    def __init__(
        self,
        dataset_path: Path | None = None,
        symbols: list[str] | None = None,
        model: str = "xgboost",
    ) -> None:
        ensure_agent_dirs()
        self.state = StateManager()
        self.vault_writer = VaultWriter()
        self.strategy_manager = StrategyManager(self.state)
        self.evaluator = Evaluator(
            state_manager=self.state,
            dataset_path=dataset_path,
            symbols=symbols,
            model=model,
        )
        self.generator = HypothesisGenerator(
            llm_client=OpenCodeClient(),
            vault_reader=VaultReader(),
            state_manager=self.state,
        )
        self.drift_monitor = DriftMonitor(
            strategy_manager=self.strategy_manager,
            state_manager=self.state,
        )

    def run_cycle(
        self,
        max_hypotheses: int = 3,
        monitor_only: bool = False,
        after_daily_eval: bool = False,
    ) -> dict:
        """Run one hybrid batch/event-driven cycle."""
        drift_events = self.drift_monitor.check()
        if monitor_only:
            self.state.mark_run()
            return {"drift_events": drift_events, "evaluations": []}
        if after_daily_eval and not _has_actionable_drift(drift_events):
            self.state.mark_run()
            return {"drift_events": drift_events, "evaluations": []}

        try:
            hypotheses = self.generator.generate(max_hypotheses=max_hypotheses)
        except LLMCallError:
            logger.exception("OpenCode hypothesis generation failed")
            self.state.mark_run()
            return {"drift_events": drift_events, "evaluations": []}

        records = []
        for hypothesis in hypotheses:
            filter_hash = hash_filters(hypothesis.filters)
            self.vault_writer.write_hypothesis(hypothesis, filter_hash)
            try:
                record = self.evaluator.evaluate(hypothesis)
            except EvaluationError:
                logger.exception("Evaluation failed for %s", filter_hash)
                continue
            self.vault_writer.write_experiment(record)
            self.vault_writer.write_learning(record)
            if record.status == "validated":
                self.strategy_manager.persist_validated(record)
            records.append(record.to_dict())

        self.state.mark_run()
        return {"drift_events": drift_events, "evaluations": records}


def _has_actionable_drift(events: list[dict]) -> bool:
    return any(event.get("status") in {"degrading", "dead"} for event in events)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Autonomous research agent.")
    parser.add_argument("--dataset", type=Path, help="Research predictions parquet")
    parser.add_argument("--symbols", help="CSV symbols used when building in memory")
    parser.add_argument("--model", default="xgboost")
    parser.add_argument("--max-hypotheses", type=int, default=3)
    parser.add_argument("--monitor-only", action="store_true")
    parser.add_argument("--after-daily-eval", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-hours", type=float, default=6.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    symbols = None
    if args.symbols:
        symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    orchestrator = ResearchOrchestrator(
        dataset_path=args.dataset,
        symbols=symbols,
        model=args.model,
    )
    while True:
        result = orchestrator.run_cycle(
            max_hypotheses=args.max_hypotheses,
            monitor_only=args.monitor_only,
            after_daily_eval=args.after_daily_eval,
        )
        logger.info("agent cycle result: %s", result)
        if not args.loop:
            return
        time.sleep(max(args.interval_hours, 0.1) * 60 * 60)


if __name__ == "__main__":
    main()
