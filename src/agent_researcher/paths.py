"""Filesystem boundaries for the autonomous research agent."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = PROJECT_ROOT / "src" / "agent_researcher"
VAULT_ROOT = PROJECT_ROOT / "vault"
AGENT_VAULT_ROOT = VAULT_ROOT / "AgentResearch"

STATE_PATH = AGENT_ROOT / "state.json"
STRATEGIES_ROOT = AGENT_ROOT / "strategies"
ACTIVE_STRATEGIES_DIR = STRATEGIES_ROOT / "active"
REJECTED_STRATEGIES_DIR = STRATEGIES_ROOT / "rejected"
PROMPTS_DIR = AGENT_ROOT / "tmp" / "prompts"

ALLOWED_WRITE_ROOTS = (AGENT_ROOT, AGENT_VAULT_ROOT)


def ensure_agent_dirs() -> None:
    """Create every directory the agent is allowed to write to."""
    for path in (
        AGENT_ROOT,
        ACTIVE_STRATEGIES_DIR,
        REJECTED_STRATEGIES_DIR,
        PROMPTS_DIR,
        AGENT_VAULT_ROOT / "logs",
        AGENT_VAULT_ROOT / "learnings",
        AGENT_VAULT_ROOT / "hypotheses",
    ):
        path.mkdir(parents=True, exist_ok=True)


def assert_agent_write_path(path: Path) -> Path:
    """Return resolved path if it stays inside an approved write root."""
    resolved = path.resolve()
    for root in ALLOWED_WRITE_ROOTS:
        root_resolved = root.resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            return resolved
    raise ValueError(f"agent write outside allowed roots blocked: {resolved}")
