"""OpenCode CLI integration for structured hypothesis generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.agent_researcher.models import Hypothesis, utc_now_iso
from src.agent_researcher.paths import PROMPTS_DIR, assert_agent_write_path


class LLMCallError(RuntimeError):
    """Raised when OpenCode cannot produce valid structured hypotheses."""


class OpenCodeClient:
    """Stateless OpenCode CLI client.

    The runtime writes prompt files only under ``src/agent_researcher/tmp``.
    """

    def __init__(
        self,
        command: str | None = None,
        model: str = "qwen/qwen/qwen3.5:9b",
        agent: str = "autotrader-researcher",
        timeout_seconds: int | None = None,
    ) -> None:
        self.command = command or os.getenv("AGENT_RESEARCH_OPENCODE_CMD", "opencode")
        self.model = os.getenv("AGENT_RESEARCH_OPENCODE_MODEL", model)
        self.agent = os.getenv("AGENT_RESEARCH_OPENCODE_AGENT", agent)
        self.timeout_seconds = timeout_seconds

    def call(self, prompt: str) -> str:
        """Send an arbitrary prompt to OpenCode and return raw stdout."""
        self._write_prompt(prompt)
        command = self._build_command()
        try:
            result = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[2],
                capture_output=True,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LLMCallError(
                f"OpenCode command not found: {self.command}. "
                "Set AGENT_RESEARCH_OPENCODE_CMD to the full executable path."
            ) from exc
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            self._dump_raw(stdout, stderr)
            raise LLMCallError(stderr.strip() or f"opencode exit {result.returncode}")
        return stdout

    def generate_hypotheses(
        self,
        context: dict[str, Any],
        max_hypotheses: int = 3,
    ) -> list[Hypothesis]:
        """Call OpenCode and parse its JSON response."""
        prompt = self.build_prompt(context, max_hypotheses=max_hypotheses)
        try:
            stdout = self.call(prompt)
        except LLMCallError:
            raise
        try:
            return parse_hypotheses_json(stdout)
        except LLMCallError:
            self._dump_raw(stdout, "")
            raise

    def build_prompt(
        self,
        context: dict[str, Any],
        max_hypotheses: int = 3,
    ) -> str:
        """Build the full stateless prompt sent to OpenCode."""
        payload = json.dumps(context, indent=2, sort_keys=True, default=str)
        return f"""
You are a senior quant researcher. Generate at most {max_hypotheses}
new conditional trading hypotheses for the AutoTrader research system.

You have access to a 100k token context window. Use it: read the full
context payload below carefully (vault notes, daily_eval breakdowns,
filter_log of past tests, active strategies, prior failures) before
proposing anything. Cross-reference recent learnings and avoid filters
that already failed in tested_filters or filter_log.

Hard rules:
- Return ONLY valid JSON, no prose and no markdown fences.
- Output must be a JSON array.
- Each item must contain: hypothesis, filters, reasoning, expected_behavior.
- Use causal reasoning, not brute-force pattern matching.
- Prefer interpretable filters supported by conditional_analysis:
  symbol, model, hour_utc, session, signal, trend, volatility_regime,
  confidence, confidence_min, session_score.
- Avoid any filter already tested or described as failed.
- Minimum expected sample size must be at least 30 trades.
- Be Bonferroni-aware: propose few, high-conviction hypotheses.
- Do not use future information or daily_eval outcomes as proof.

Context:
{payload}
""".strip()

    def _dump_raw(self, stdout: str, stderr: str) -> None:
        stamp = utc_now_iso().replace(":", "").replace("+", "Z")
        path = PROMPTS_DIR / f"raw_output_{stamp}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"--- STDOUT ---\n{stdout}\n--- STDERR ---\n{stderr}",
            encoding="utf-8",
        )

    def _write_prompt(self, prompt: str) -> Path:
        stamp = utc_now_iso().replace(":", "").replace("+", "Z")
        path = assert_agent_write_path(PROMPTS_DIR / f"hypothesis_{stamp}.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
        return path

    def _build_command(self) -> list[str]:
        """Build the subprocess argv for the opencode call.

        The prompt is delivered via stdin to bypass the Windows 8KB
        command-line length limit. On Windows the npm-installed
        ``opencode.CMD`` shim mangles model ids containing both ``/``
        and ``:`` when invoked through ``cmd.exe`` (the value reaches
        yargs truncated to ``qwen/`` and the call fails with
        ``ProviderModelNotFoundError``). The shim is also unusable from
        WSL bash because it would need ``node`` on the WSL side. The
        only reliable path on Windows is to invoke ``node`` directly
        with the opencode entrypoint script that the shim wraps.
        """
        resolved = shutil.which(self.command)
        if sys.platform == "win32" and _needs_cmd_wrapper(resolved, self.command):
            node, script = _resolve_windows_node_invocation(
                resolved or self.command,
            )
            return [
                node, script, "run",
                "--agent", self.agent,
                "--model", self.model,
            ]
        return [
            resolved or self.command, "run",
            "--agent", self.agent,
            "--model", self.model,
        ]


def parse_hypotheses_json(text: str) -> list[Hypothesis]:
    """Parse JSON even if the CLI accidentally wraps it in light prose."""
    raw = _extract_json_array(text)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMCallError(f"invalid JSON from OpenCode: {exc}") from exc
    if not isinstance(payload, list):
        raise LLMCallError("OpenCode response must be a JSON array")

    hypotheses: list[Hypothesis] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        filters = item.get("filters")
        if not isinstance(filters, dict):
            continue
        required = ("hypothesis", "reasoning", "expected_behavior")
        if not all(isinstance(item.get(key), str) for key in required):
            continue
        hypotheses.append(
            Hypothesis(
                hypothesis=item["hypothesis"].strip(),
                filters=filters,
                reasoning=item["reasoning"].strip(),
                expected_behavior=item["expected_behavior"].strip(),
            )
        )
    if not hypotheses:
        raise LLMCallError("OpenCode response contained no valid hypotheses")
    return hypotheses


def _extract_json_array(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise LLMCallError("no JSON array found in OpenCode output")
    return stripped[start:end + 1]


def _resolve_windows_node_invocation(cmd_path: str) -> tuple[str, str]:
    """Return (node_exe, opencode_script) bypassing the npm .CMD shim.

    Honours ``AGENT_RESEARCH_NODE_EXE`` and ``AGENT_RESEARCH_OPENCODE_SCRIPT``
    when set; otherwise auto-detects ``node`` from PATH and assumes the
    opencode-ai package sits next to the resolved ``opencode.CMD``.
    """
    node = os.getenv("AGENT_RESEARCH_NODE_EXE") or shutil.which("node") or "node"
    script_env = os.getenv("AGENT_RESEARCH_OPENCODE_SCRIPT")
    if script_env:
        return node, script_env
    cmd = Path(cmd_path)
    candidate = cmd.parent / "node_modules" / "opencode-ai" / "bin" / "opencode"
    if not candidate.exists():
        raise LLMCallError(
            f"could not locate opencode entrypoint near {cmd_path}. "
            "Set AGENT_RESEARCH_OPENCODE_SCRIPT to the JS bin path."
        )
    return node, str(candidate)


def _needs_cmd_wrapper(resolved: str | None, command: str) -> bool:
    """Return True for Windows shell shims such as opencode.cmd."""
    target = (resolved or command).lower()
    return resolved is None or target.endswith((".bat", ".cmd"))
