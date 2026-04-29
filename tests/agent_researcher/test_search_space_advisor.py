import json

import pytest

from src.agent_researcher.llm_interface import LLMCallError
from src.agent_researcher.search_space_advisor import (
    DEFAULT_SEARCH_SPACES,
    SearchSpaceAdvisor,
    _parse_response,
    _validate_param_spec,
    load_search_space,
)


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

def test_parse_response_extracts_json_object():
    text = '{"xgboost": {"dollar_majors": {"params": {}, "reasoning": "ok"}}}'
    result = _parse_response(text)
    assert "xgboost" in result


def test_parse_response_strips_markdown_fences():
    text = '```json\n{"xgboost": {}}\n```'
    result = _parse_response(text)
    assert "xgboost" in result


def test_parse_response_raises_on_no_object():
    with pytest.raises(LLMCallError):
        _parse_response("no json here")


def test_parse_response_raises_on_array_instead_of_object():
    with pytest.raises((LLMCallError, json.JSONDecodeError)):
        _parse_response("[1, 2, 3]")


# ---------------------------------------------------------------------------
# _validate_param_spec
# ---------------------------------------------------------------------------

def test_validate_param_spec_accepts_valid_int_spec():
    spec = {"type": "int", "low": 2, "high": 6}
    assert _validate_param_spec(spec, "xgboost", "max_depth") is True


def test_validate_param_spec_accepts_valid_float_spec():
    spec = {"type": "float", "low": 0.01, "high": 0.2, "log": True}
    assert _validate_param_spec(spec, "xgboost", "learning_rate") is True


def test_validate_param_spec_rejects_unknown_param():
    spec = {"type": "int", "low": 1, "high": 5}
    assert _validate_param_spec(spec, "xgboost", "nonexistent_param") is False


def test_validate_param_spec_rejects_low_gte_high():
    spec = {"type": "int", "low": 5, "high": 2}
    assert _validate_param_spec(spec, "xgboost", "max_depth") is False


def test_validate_param_spec_rejects_widening_range():
    defaults = DEFAULT_SEARCH_SPACES["xgboost"]["max_depth"]
    spec = {"type": "int", "low": defaults["low"] - 1, "high": defaults["high"] + 1}
    assert _validate_param_spec(spec, "xgboost", "max_depth") is False


# ---------------------------------------------------------------------------
# load_search_space
# ---------------------------------------------------------------------------

def test_load_search_space_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.agent_researcher.search_space_advisor.SEARCH_SPACES_DIR", tmp_path)
    assert load_search_space("xgboost", "dollar_majors") is None


def test_load_search_space_returns_params_when_saved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.agent_researcher.search_space_advisor.SEARCH_SPACES_DIR", tmp_path)
    data = {
        "model_name": "xgboost",
        "group_name": "dollar_majors",
        "params": {"max_depth": {"type": "int", "low": 2, "high": 4}},
        "reasoning": "narrow",
        "updated_at": "2026-01-01",
    }
    (tmp_path / "xgboost_dollar_majors.json").write_text(json.dumps(data), encoding="utf-8")

    result = load_search_space("xgboost", "dollar_majors")

    assert result == data["params"]


# ---------------------------------------------------------------------------
# SearchSpaceAdvisor.advise
# ---------------------------------------------------------------------------

def _make_advisor(llm_response: str) -> SearchSpaceAdvisor:
    from unittest.mock import MagicMock

    client = MagicMock()
    client.call.return_value = llm_response
    return SearchSpaceAdvisor(llm_client=client)


def test_advise_skips_when_no_hpo_data():
    advisor = _make_advisor("{}")
    result = advisor.advise({})
    assert result["updated"] == 0


def test_advise_saves_valid_search_space(tmp_path, monkeypatch):
    monkeypatch.setattr("src.agent_researcher.search_space_advisor.SEARCH_SPACES_DIR", tmp_path)
    payload = {
        "xgboost": {
            "dollar_majors": {
                "params": {
                    "max_depth": {"type": "int", "low": 2, "high": 5},
                },
                "reasoning": "top trials cluster at depth 2-4",
            }
        }
    }
    advisor = _make_advisor(json.dumps(payload))
    hpo_summary = {"top_trials_by_study": {"hpo_xgboost_dollar_majors": [{"score": 0.7}]}}

    result = advisor.advise(hpo_summary)

    assert result["updated"] == 1
    assert result["errors"] == 0
    saved = load_search_space("xgboost", "dollar_majors")
    assert saved is not None


def test_advise_skips_invalid_params(tmp_path, monkeypatch):
    monkeypatch.setattr("src.agent_researcher.search_space_advisor.SEARCH_SPACES_DIR", tmp_path)
    payload = {
        "xgboost": {
            "dollar_majors": {
                "params": {
                    "max_depth": {"type": "int", "low": 100, "high": 200},  # out of default bounds
                },
                "reasoning": "bad range",
            }
        }
    }
    advisor = _make_advisor(json.dumps(payload))
    hpo_summary = {"top_trials_by_study": {"hpo_xgboost_dollar_majors": [{"score": 0.7}]}}

    result = advisor.advise(hpo_summary)

    assert result["updated"] == 0
    assert result["skipped"] == 1


def test_advise_handles_llm_error(monkeypatch):
    from unittest.mock import MagicMock

    client = MagicMock()
    client.call.side_effect = LLMCallError("connection failed")
    advisor = SearchSpaceAdvisor(llm_client=client)
    hpo_summary = {"top_trials_by_study": {"hpo_xgboost_dollar_majors": []}}

    result = advisor.advise(hpo_summary)

    assert result["errors"] == 1
    assert result["updated"] == 0
