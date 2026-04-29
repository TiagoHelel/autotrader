"""
LLM-driven search space advisor.

Reads HPO results (top trials, param patterns, current champions) and asks
the LLM to suggest narrowed/shifted hyperparameter ranges for the next
Optuna run. Results are saved to data/hpo/search_spaces/ as JSON files.

The LLM acts as strategist: it interprets *why* certain param regions win
and adjusts the search accordingly. Optuna stays as the executor within
those bounds.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.agent_researcher.llm_interface import LLMCallError, OpenCodeClient
from src.agent_researcher.models import utc_now_iso

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEARCH_SPACES_DIR = PROJECT_ROOT / "data" / "hpo" / "search_spaces"

# Default ranges — used as fallback and shown to LLM as current baseline
DEFAULT_SEARCH_SPACES: dict[str, dict[str, dict]] = {
    "xgboost": {
        "n_estimators":      {"type": "int",   "low": 50,    "high": 500},
        "max_depth":         {"type": "int",   "low": 2,     "high": 8},
        "learning_rate":     {"type": "float", "low": 0.01,  "high": 0.3,  "log": True},
        "subsample":         {"type": "float", "low": 0.5,   "high": 1.0},
        "colsample_bytree":  {"type": "float", "low": 0.5,   "high": 1.0},
        "reg_lambda":        {"type": "float", "low": 0.1,   "high": 10.0, "log": True},
    },
    "random_forest": {
        "n_estimators":      {"type": "int",   "low": 50,    "high": 400},
        "max_depth":         {"type": "int",   "low": 3,     "high": 15},
        "min_samples_leaf":  {"type": "int",   "low": 5,     "high": 50},
    },
}


def load_search_space(model_name: str, group_name: str) -> dict[str, dict] | None:
    """Load a saved search space for (model, group), or None if not found."""
    path = SEARCH_SPACES_DIR / f"{model_name}_{group_name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("params")
    except (OSError, json.JSONDecodeError):
        return None


def _save_search_space(
    model_name: str,
    group_name: str,
    params: dict[str, dict],
    reasoning: str,
) -> None:
    SEARCH_SPACES_DIR.mkdir(parents=True, exist_ok=True)
    path = SEARCH_SPACES_DIR / f"{model_name}_{group_name}.json"
    data = {
        "model_name": model_name,
        "group_name": group_name,
        "params": params,
        "reasoning": reasoning,
        "updated_at": utc_now_iso(),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Search space saved: %s", path)


def _build_prompt(hpo_summary: dict[str, Any]) -> str:
    defaults_json = json.dumps(DEFAULT_SEARCH_SPACES, indent=2)
    summary_json = json.dumps(hpo_summary, indent=2, default=str)
    return f"""
You are a senior quant researcher optimizing ML hyperparameter search spaces
for a FOREX algorithmic trading system.

Below you have:
1. The current (default) Optuna search space ranges for each model.
2. HPO results: current champions, top trials per study, and parameter patterns.

Your job: for each (model_name, symbol_group) that has at least 5 top trials,
suggest a NARROWED or SHIFTED search space. The goal is to focus the next
round of Optuna trials on the regions that have proven to work.

Rules:
- Return ONLY a valid JSON object. No prose, no markdown fences.
- Only output entries where you have enough data to justify a change.
- New ranges must be WITHIN the default bounds shown below (never widen).
- Prefer narrowing by 20-40% around the median of the top-5 trials.
- If a parameter shows no clear pattern, keep the default range.
- Include a "reasoning" string per entry explaining the change.

Output format:
{{
  "xgboost": {{
    "dollar_majors": {{
      "params": {{
        "max_depth":     {{"type": "int",   "low": 2, "high": 4}},
        "learning_rate": {{"type": "float", "low": 0.01, "high": 0.1, "log": true}},
        "n_estimators":  {{"type": "int",   "low": 100, "high": 300}}
      }},
      "reasoning": "top-5 trials cluster at max_depth 2-3 and lr 0.02-0.08"
    }}
  }},
  "random_forest": {{
    "yen_crosses": {{
      "params": {{ ... }},
      "reasoning": "..."
    }}
  }}
}}

Default search spaces (current baseline):
{defaults_json}

HPO results context:
{summary_json}
""".strip()


def _parse_response(text: str) -> dict[str, Any]:
    """Extract and validate the JSON object from LLM output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMCallError("no JSON object found in search space advisor output")
    payload = json.loads(stripped[start:end + 1])
    if not isinstance(payload, dict):
        raise LLMCallError("search space response must be a JSON object")
    return payload


def _validate_param_spec(spec: dict, model_name: str, param_name: str) -> bool:
    """Return True if a param spec is structurally valid and within defaults."""
    defaults = DEFAULT_SEARCH_SPACES.get(model_name, {}).get(param_name)
    if defaults is None:
        return False
    required = {"type", "low", "high"}
    if not required.issubset(spec.keys()):
        return False
    try:
        if spec["low"] < defaults["low"] or spec["high"] > defaults["high"]:
            return False
        if spec["low"] >= spec["high"]:
            return False
    except (TypeError, KeyError):
        return False
    return True


class SearchSpaceAdvisor:
    """Ask the LLM to suggest Optuna search space adjustments."""

    def __init__(self, llm_client: OpenCodeClient) -> None:
        self.llm_client = llm_client

    def advise(self, hpo_summary: dict[str, Any]) -> dict[str, int]:
        """
        Generate and persist search space adjustments.

        Returns a count dict: {"updated": N, "skipped": M, "errors": K}
        """
        if not hpo_summary or not hpo_summary.get("top_trials_by_study"):
            logger.info("SearchSpaceAdvisor: no HPO data yet, skipping")
            return {"updated": 0, "skipped": 0, "errors": 0}

        prompt = _build_prompt(hpo_summary)
        try:
            raw = self.llm_client.call(prompt)
        except LLMCallError:
            logger.exception("SearchSpaceAdvisor: LLM call failed")
            return {"updated": 0, "skipped": 0, "errors": 1}

        try:
            payload = _parse_response(raw)
        except (LLMCallError, json.JSONDecodeError):
            logger.exception("SearchSpaceAdvisor: could not parse LLM response")
            return {"updated": 0, "skipped": 0, "errors": 1}

        updated = skipped = errors = 0

        for model_name, groups in payload.items():
            if not isinstance(groups, dict):
                continue
            for group_name, entry in groups.items():
                if not isinstance(entry, dict):
                    skipped += 1
                    continue
                params = entry.get("params", {})
                reasoning = entry.get("reasoning", "")
                validated = {}
                for param_name, spec in params.items():
                    if not isinstance(spec, dict):
                        continue
                    if _validate_param_spec(spec, model_name, param_name):
                        validated[param_name] = spec
                    else:
                        logger.warning(
                            "SearchSpaceAdvisor: rejected %s/%s param=%s spec=%s",
                            model_name, group_name, param_name, spec,
                        )

                if not validated:
                    skipped += 1
                    continue

                try:
                    _save_search_space(model_name, group_name, validated, reasoning)
                    updated += 1
                    logger.info(
                        "SearchSpaceAdvisor: updated %s/%s (%d params) — %s",
                        model_name, group_name, len(validated), reasoning[:80],
                    )
                except Exception:
                    logger.exception(
                        "SearchSpaceAdvisor: failed to save %s/%s", model_name, group_name
                    )
                    errors += 1

        return {"updated": updated, "skipped": skipped, "errors": errors}
