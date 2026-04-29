"""
Nightly HPO script.

Runs Optuna trials for all (model x symbol_group) combinations using cached
feature parquets — no MT5 connection required.

After running HPO trials, evaluates promotion for all pairs (champion/challenger).

Usage:
    python scripts/run_hpo.py
    python scripts/run_hpo.py --n-trials 100
    python scripts/run_hpo.py --hpo-only       # skip promotion step
    python scripts/run_hpo.py --promote-only   # skip HPO, only evaluate promotion
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly HPO + promotion runner")
    parser.add_argument("--n-trials", type=int, default=50,
                        help="Optuna trials per (model x group) study")
    parser.add_argument("--hpo-only", action="store_true",
                        help="Run HPO trials only, skip promotion")
    parser.add_argument("--promote-only", action="store_true",
                        help="Skip HPO trials, only evaluate promotions")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_hpo")

    if not args.promote_only:
        logger.info("=== HPO trials start (n_trials_per_study=%d) ===", args.n_trials)
        from src.training.hpo_runner import run_nightly_hpo
        hpo_results = run_nightly_hpo(n_trials_per_study=args.n_trials)
        completed = sum(1 for r in hpo_results if not r.get("skipped"))
        logger.info("HPO done: %d/%d studies ran", completed, len(hpo_results))

    if not args.hpo_only:
        logger.info("=== Promotion evaluation start ===")
        from src.training.promoter import run_promotion_cycle
        promotions = run_promotion_cycle()
        promoted = [p for p in promotions if p.get("action") == "promoted"]
        logger.info(
            "Promotion done: %d promoted, %d no_change, %d skipped/rejected",
            len(promoted),
            sum(1 for p in promotions if p.get("action") == "no_change"),
            sum(1 for p in promotions if p.get("action") in ("skipped", "rejected")),
        )
        if promoted:
            logger.info("Newly promoted:\n%s", json.dumps(promoted, indent=2))


if __name__ == "__main__":
    main()
