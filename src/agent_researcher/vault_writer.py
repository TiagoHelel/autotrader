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

    AREA_INDEX_LINK = "AgentResearch/README"
    FOLDER_INDEX_NAME = "_index"

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
            *self._related_block("hypotheses", filter_hash, hypothesis.hypothesis),
        ]
        out = self._write(path, "\n".join(body))
        self._refresh_folder_index("hypotheses")
        return out

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
            *self._related_block("logs", record.filter_hash, record.hypothesis.hypothesis),
        ]
        out = self._write(path, "\n".join(body))
        self._refresh_folder_index("logs")
        return out

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
            *self._related_block("learnings", record.filter_hash, record.hypothesis.hypothesis),
        ]
        out = self._write(path, "\n".join(body))
        self._refresh_folder_index("learnings")
        return out

    def _path(self, folder: str, filter_hash: str, title: str) -> Path:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:80]
        name = f"{filter_hash}-{slug or 'hypothesis'}.md"
        return assert_agent_write_path(self.root / folder / name)

    _RELATED_LABELS: dict[str, str] = {
        "hypotheses": "Hypothesis",
        "learnings": "Learning",
        "logs": "Experiment log",
    }

    def _related_block(
        self, current_folder: str, filter_hash: str, title: str
    ) -> list[str]:
        """Wikilinks Obsidian para os irmaos do mesmo `filter_hash` + MOCs.

        Usa path completo (`pasta/stem`) em todos os wikilinks porque os 3
        arquivos do mesmo trio compartilham o mesmo stem e Obsidian nao
        resolveria links ambiguos.
        """
        others = [f for f in self._RELATED_LABELS if f != current_folder]
        lines = ["## Related", ""]
        for folder in others:
            stem = self._path(folder, filter_hash, title).stem
            label = self._RELATED_LABELS[folder]
            lines.append(f"- {label}: [[{folder}/{stem}]]")
        # MOCs: pasta atual e area-level.
        lines.append(
            f"- Folder: [[AgentResearch/{current_folder}/{self.FOLDER_INDEX_NAME}|{current_folder}]]"
        )
        lines.append(f"- Area: [[{self.AREA_INDEX_LINK}|AgentResearch]]")
        lines.append("")
        return lines

    def _refresh_folder_index(self, folder: str) -> Path:
        """(Re)gera `_index.md` listando todos os arquivos do folder."""
        folder_path = self.root / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        children = sorted(
            p for p in folder_path.glob("*.md") if p.stem != self.FOLDER_INDEX_NAME
        )
        label = self._RELATED_LABELS.get(folder, folder)
        body = [
            "---",
            "type: agent-research-folder-index",
            f"folder: {folder}",
            "tags: [agent-research, index]",
            "---",
            "",
            f"# {folder.capitalize()}",
            "",
            f"Auto-generated index. Lists every {label.lower()} file in this folder.",
            "",
            f"## {label} files ({len(children)})",
            "",
        ]
        if not children:
            body.append("_None yet._")
        else:
            for child in children:
                body.append(f"- [[{folder}/{child.stem}]]")
        body.append("")
        body.append("## Related")
        body.append("")
        body.append(f"- Area: [[{self.AREA_INDEX_LINK}|AgentResearch]]")
        body.append("")
        index_path = assert_agent_write_path(
            folder_path / f"{self.FOLDER_INDEX_NAME}.md"
        )
        return self._write(index_path, "\n".join(body))

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
