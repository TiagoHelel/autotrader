"""Write agent-owned Obsidian notes for experiments and learnings."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.agent_researcher.models import EvaluationRecord, Hypothesis, utc_now_iso
from src.agent_researcher.paths import AGENT_VAULT_ROOT, assert_agent_write_path


class VaultWriter:
    """Persist markdown notes under vault/AgentResearch."""

    def __init__(self, root: Path = AGENT_VAULT_ROOT) -> None:
        self.root = root

    def write_hypothesis(self, hypothesis: Hypothesis, filter_hash: str) -> Path:
        """Write the pre-test hypothesis note."""
        path = self._path("hypotheses", filter_hash, hypothesis.hypothesis)
        body = [
            "---",
            "type: agent-hypothesis",
            f"created: {utc_now_iso()}",
            f"filter_hash: {filter_hash}",
            "status: generated",
            "tags: [agent-research, hypothesis]",
            "---",
            "",
            f"# {hypothesis.hypothesis}",
            "",
            "## Filters",
            "",
            "```json",
            json.dumps(hypothesis.filters, indent=2, sort_keys=True),
            "```",
            "",
            "## Causal reasoning",
            "",
            hypothesis.reasoning,
            "",
            "## Expected behavior",
            "",
            hypothesis.expected_behavior,
            "",
        ]
        return self._write(path, "\n".join(body))

    def write_experiment(self, record: EvaluationRecord) -> Path:
        """Write a full experiment log after research and optional holdout."""
        path = self._path("logs", record.filter_hash, record.hypothesis.hypothesis)
        body = [
            "---",
            "type: agent-experiment",
            f"created: {record.created_at}",
            f"filter_hash: {record.filter_hash}",
            f"status: {record.status}",
            f"verdict: {record.verdict}",
            "tags: [agent-research, experiment]",
            "---",
            "",
            f"# {record.hypothesis.hypothesis}",
            "",
            "## Filters",
            "",
            "```json",
            json.dumps(record.hypothesis.filters, indent=2, sort_keys=True),
            "```",
            "",
            "## Research result",
            "",
            self._result_block(record.research),
            "",
            "## Holdout result",
            "",
            self._result_block(record.holdout),
            "",
            "## Verdict",
            "",
            record.verdict,
            "",
            "## Insight",
            "",
            record.insight,
            "",
        ]
        return self._write(path, "\n".join(body))

    def write_learning(self, record: EvaluationRecord) -> Path:
        """Write a distilled learning for future prompt context."""
        path = self._path("learnings", record.filter_hash, record.hypothesis.hypothesis)
        body = [
            "---",
            "type: agent-learning",
            f"created: {utc_now_iso()}",
            f"filter_hash: {record.filter_hash}",
            f"verdict: {record.verdict}",
            "tags: [agent-research, learning]",
            "---",
            "",
            f"# Learning - {record.hypothesis.hypothesis}",
            "",
            record.insight,
            "",
            "## Filters",
            "",
            "```json",
            json.dumps(record.hypothesis.filters, indent=2, sort_keys=True),
            "```",
            "",
        ]
        return self._write(path, "\n".join(body))

    def _path(self, folder: str, filter_hash: str, title: str) -> Path:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:80]
        name = f"{filter_hash}-{slug or 'hypothesis'}.md"
        return assert_agent_write_path(self.root / folder / name)

    def _write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    @staticmethod
    def _result_block(result: object | None) -> str:
        if result is None:
            return "_Not run._"
        to_dict = getattr(result, "to_dict")
        payload = to_dict()
        return "\n".join(
            [
                "```json",
                json.dumps(payload, indent=2, sort_keys=True),
                "```",
            ]
        )
