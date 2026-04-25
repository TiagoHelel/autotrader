"""
Wrapper schedulable for the autonomous research agent.

Runtime writes performed by the agent are restricted to:
- src/agent_researcher/**
- vault/AgentResearch/**

Usage:
    python scripts/run_agent_researcher.py
    python scripts/run_agent_researcher.py --after-daily-eval
    python scripts/run_agent_researcher.py --monitor-only
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent_researcher.orchestrator import main  # noqa: E402


if __name__ == "__main__":
    main()
