"""Autonomous research agent for conditional trading hypotheses.

The package is intentionally isolated: runtime writes are restricted to
``src/agent_researcher`` and ``vault/AgentResearch``.
"""

from src.agent_researcher.models import EvaluationRecord, Hypothesis

__all__ = ["EvaluationRecord", "Hypothesis"]
