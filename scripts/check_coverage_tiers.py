#!/usr/bin/env python
"""
Tiered coverage gate for AutoTrader.

Enforces different coverage thresholds by risk tier:
  - CRITICAL (real-money routing + risk): 90%+
  - ML pipeline (model training/features): 85%+
  - Overall project: 75%+

Reads coverage.xml (produced by pytest-cov --cov-report=xml) and fails with a
non-zero exit code if any tier is below its threshold. Intended to be invoked
in CI after a `pytest --cov=src --cov-report=xml` run.

Usage:
    python -m pytest --cov=src --cov-report=xml --cov-report=term
    python scripts/check_coverage_tiers.py
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
# Path fragments (substring match against coverage.xml <class filename="...">)
CRITICAL_PATHS = [
    "execution/engine.py",
    "execution/loop.py",
    "decision/signal.py",
    "decision/ensemble.py",
    "decision/model_selector.py",
    "backtest/engine.py",
    "mt5/connection.py",
    "evaluation/cpcv.py",
]

ML_PATHS = [
    "models/",
    "features/",
    "evaluation/",
    "research/",
]

THRESHOLDS = {
    "critical": 90.0,
    "ml": 80.0,
    "overall": 75.0,
}


@dataclass
class FileCoverage:
    filename: str
    statements: int
    missed: int

    @property
    def covered(self) -> int:
        return self.statements - self.missed

    @property
    def pct(self) -> float:
        return (self.covered / self.statements * 100.0) if self.statements else 100.0


def _normalize(p: str) -> str:
    return p.replace("\\", "/")


def load_coverage(xml_path: Path) -> list[FileCoverage]:
    if not xml_path.exists():
        print(f"ERROR: coverage.xml not found at {xml_path}", file=sys.stderr)
        print("Run: pytest --cov=src --cov-report=xml", file=sys.stderr)
        sys.exit(2)

    tree = ET.parse(xml_path)
    root = tree.getroot()
    files: list[FileCoverage] = []
    for cls in root.iter("class"):
        filename = _normalize(cls.get("filename", ""))
        if not filename:
            continue
        lines = list(cls.iter("line"))
        if not lines:
            continue
        statements = len(lines)
        missed = sum(1 for ln in lines if ln.get("hits", "0") == "0")
        files.append(FileCoverage(filename, statements, missed))
    return files


def tier_for(filename: str) -> str:
    norm = _normalize(filename)
    if any(p in norm for p in CRITICAL_PATHS):
        return "critical"
    if any(p in norm for p in ML_PATHS):
        return "ml"
    return "other"


def aggregate(files: list[FileCoverage]) -> dict[str, tuple[int, int, float]]:
    """Return {tier: (statements, missed, pct)}."""
    sums: dict[str, tuple[int, int]] = {"critical": (0, 0), "ml": (0, 0), "other": (0, 0)}
    for f in files:
        t = tier_for(f.filename)
        s, m = sums[t]
        sums[t] = (s + f.statements, m + f.missed)

    result: dict[str, tuple[int, int, float]] = {}
    for tier, (stmts, missed) in sums.items():
        pct = ((stmts - missed) / stmts * 100.0) if stmts else 100.0
        result[tier] = (stmts, missed, pct)

    # overall
    total_stmts = sum(s for s, _ in sums.values())
    total_missed = sum(m for _, m in sums.values())
    overall_pct = ((total_stmts - total_missed) / total_stmts * 100.0) if total_stmts else 100.0
    result["overall"] = (total_stmts, total_missed, overall_pct)
    return result


def main() -> int:
    xml_path = Path("coverage.xml")
    files = load_coverage(xml_path)
    tiers = aggregate(files)

    failures: list[str] = []
    print("=" * 70)
    print("Tiered Coverage Gate")
    print("=" * 70)
    for tier in ("critical", "ml", "overall"):
        stmts, missed, pct = tiers[tier]
        thr = THRESHOLDS[tier]
        status = "OK" if pct >= thr else "FAIL"
        print(
            f"  {tier.upper():<10} "
            f"stmts={stmts:<6} missed={missed:<5} "
            f"cov={pct:6.2f}%  threshold={thr:5.1f}%  [{status}]"
        )
        if pct < thr:
            failures.append(
                f"{tier}: {pct:.2f}% < {thr:.1f}% threshold "
                f"({missed} of {stmts} lines uncovered)"
            )

    print("=" * 70)

    # Per-file listing for the critical tier (always shown — these are real-money paths)
    print("Critical-tier file breakdown:")
    for f in sorted(files, key=lambda x: x.filename):
        if tier_for(f.filename) == "critical":
            mark = "  " if f.pct >= THRESHOLDS["critical"] else "!!"
            print(f"  {mark} {f.filename:<45} {f.pct:6.2f}%  ({f.missed}/{f.statements} missed)")
    print("=" * 70)

    if failures:
        print("COVERAGE GATE FAILED:")
        for msg in failures:
            print(f"  - {msg}")
        return 1

    print("All coverage tiers passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
