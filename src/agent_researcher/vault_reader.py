"""Read Obsidian research notes as structured context for the LLM."""

from __future__ import annotations

from pathlib import Path

from src.agent_researcher.paths import AGENT_VAULT_ROOT, VAULT_ROOT


class VaultReader:
    """Load prior hypotheses, failures, and successful patterns."""

    def __init__(
        self,
        agent_vault_root: Path = AGENT_VAULT_ROOT,
        vault_root: Path = VAULT_ROOT,
    ) -> None:
        self.agent_vault_root = agent_vault_root
        self.vault_root = vault_root

    def load_context(self, max_files: int = 50) -> dict[str, list[dict[str, str]]]:
        """Return compact note snippets for prompt context."""
        return {
            "agent_hypotheses": self._read_notes(
                self.agent_vault_root / "hypotheses",
                max_files=max_files,
            ),
            "agent_learnings": self._read_notes(
                self.agent_vault_root / "learnings",
                max_files=max_files,
            ),
            "legacy_hypotheses": self._read_notes(
                self.vault_root / "Hypotheses",
                max_files=max_files,
            ),
        }

    def _read_notes(self, directory: Path, max_files: int) -> list[dict[str, str]]:
        if not directory.exists():
            return []
        notes: list[dict[str, str]] = []
        for path in sorted(directory.glob("*.md"), reverse=True)[:max_files]:
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            notes.append(
                {
                    "path": str(path.relative_to(self.vault_root)),
                    "title": path.stem,
                    "snippet": text[:8000],
                }
            )
        return notes
