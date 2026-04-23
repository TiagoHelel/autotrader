"""
Tests for src/llm/news_sentiment.py — LLM sentiment analysis.

Estratégia: mock do httpx para não chamar LLM real. Testa parsing,
validação, cache, fallback, cooldown, save/load.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from config.settings import settings
from src.llm.news_sentiment import (
    _parse_llm_response,
    _validate_result,
    _fallback_sentiment,
    _extract_content,
    _is_sticky_failure,
    _backend_in_cooldown,
    _mark_backend_unavailable,
    _clear_backend_cooldown,
    _backend_cooldowns,
    _llm_cache,
    _backend_skip_modes,
    get_llm_sentiment,
    process_news_with_llm,
    save_llm_features,
    load_llm_features,
    LLMBackend,
    BACKEND_COOLDOWN_SECONDS,
    shutdown_event,
    LLMShutdown,
)


@pytest.fixture(autouse=True)
def clean_state():
    """Limpa estado global entre testes."""
    _llm_cache.clear()
    _backend_cooldowns.clear()
    _backend_skip_modes.clear()
    shutdown_event.clear()
    yield
    _llm_cache.clear()
    _backend_cooldowns.clear()
    _backend_skip_modes.clear()
    shutdown_event.clear()


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    # LLM_FEATURES_DIR é avaliado no import — precisa monkeypatch direto
    import src.llm.news_sentiment as mod
    monkeypatch.setattr(mod, "LLM_FEATURES_DIR", tmp_path / "data" / "news")
    return tmp_path


# ===================== _parse_llm_response =====================

class TestParseLlmResponse:
    def test_plain_json(self):
        content = '{"sentiment_score": 0.5, "confidence": 0.8}'
        result = _parse_llm_response(content)
        assert result["sentiment_score"] == 0.5

    def test_markdown_code_block(self):
        content = '```json\n{"sentiment_score": -0.3}\n```'
        result = _parse_llm_response(content)
        assert result["sentiment_score"] == -0.3

    def test_json_embedded_in_text(self):
        content = 'Here is the result: {"sentiment_score": 0.1} end'
        result = _parse_llm_response(content)
        assert result["sentiment_score"] == 0.1

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("not json at all")


# ===================== _validate_result =====================

class TestValidateResult:
    def test_clamps_values(self):
        r = _validate_result({
            "sentiment_score": 5.0,  # > 1
            "confidence": -0.5,      # < 0
            "volatility_impact": 2.0, # > 1
        })
        assert r["sentiment_score"] == 1.0
        assert r["confidence"] == 0.0
        assert r["volatility_impact"] == 1.0

    def test_defaults(self):
        r = _validate_result({})
        assert r["sentiment_score"] == 0.0
        assert r["confidence"] == 0.5
        assert r["event_type"] == "other"
        assert r["used_fallback"] is False

    def test_truncates_reasoning(self):
        r = _validate_result({"reasoning_short": "x" * 200})
        assert len(r["reasoning_short"]) == 120


# ===================== _fallback_sentiment =====================

class TestFallbackSentiment:
    def test_schema(self):
        r = _fallback_sentiment("test news")
        assert r["used_fallback"] is True
        assert r["sentiment_score"] == 0.0
        assert r["llm_backend"] == "heuristic_fallback"


# ===================== _extract_content =====================

class TestExtractContent:
    def test_responses_api_output_text(self):
        data = {"output_text": "  some result  "}
        assert _extract_content(data, "openai-responses") == "some result"

    def test_responses_api_nested_output(self):
        data = {
            "output_text": "",
            "output": [{"content": [{"type": "text", "text": "nested"}]}],
        }
        assert _extract_content(data, "openai-responses") == "nested"

    def test_responses_api_only_reasoning_raises(self):
        data = {
            "output": [{"type": "reasoning", "summary": [{"text": "thinking..."}]}],
        }
        with pytest.raises(ValueError, match="apenas reasoning"):
            _extract_content(data, "openai-responses")

    def test_responses_api_empty_raises(self):
        data = {"output": []}
        with pytest.raises(ValueError, match="Resposta vazia"):
            _extract_content(data, "openai-responses")

    def test_chat_completions_string(self):
        data = {"choices": [{"message": {"content": "hello"}}]}
        assert _extract_content(data, "chat-completions") == "hello"

    def test_chat_completions_list_content(self):
        data = {"choices": [{"message": {"content": [
            {"type": "text", "text": "part1"},
            {"type": "text", "text": "part2"},
        ]}}]}
        assert "part1" in _extract_content(data, "chat-completions")

    def test_chat_completions_only_reasoning_raises(self):
        data = {"choices": [{"message": {"content": "", "reasoning": "thinking"}}]}
        with pytest.raises(ValueError, match="apenas reasoning"):
            _extract_content(data, "chat-completions")

    def test_chat_completions_empty_raises(self):
        data = {"choices": [{"message": {"content": ""}}]}
        with pytest.raises(ValueError, match="Resposta vazia"):
            _extract_content(data, "chat-completions")


# ===================== Cooldown =====================

class TestCooldown:
    def test_not_in_cooldown_by_default(self):
        backend = LLMBackend("test", "http://x", "key", "model")
        assert not _backend_in_cooldown(backend)

    def test_mark_and_check(self):
        backend = LLMBackend("test", "http://x", "key", "model")
        _mark_backend_unavailable(backend, RuntimeError("fail"))
        assert _backend_in_cooldown(backend)

    def test_clear_cooldown(self):
        backend = LLMBackend("test", "http://x", "key", "model")
        _mark_backend_unavailable(backend, RuntimeError("fail"))
        _clear_backend_cooldown(backend)
        assert not _backend_in_cooldown(backend)

    def test_expired_cooldown(self):
        backend = LLMBackend("test", "http://x", "key", "model")
        _backend_cooldowns["test"] = datetime.utcnow() - timedelta(seconds=1)
        assert not _backend_in_cooldown(backend)


# ===================== _is_sticky_failure =====================

class TestIsStickyFailure:
    def test_reasoning_only(self):
        assert _is_sticky_failure(ValueError("apenas reasoning sem output"))

    def test_empty_response(self):
        assert _is_sticky_failure(ValueError("Resposta vazia"))

    def test_transient(self):
        assert not _is_sticky_failure(RuntimeError("timeout"))


# ===================== get_llm_sentiment =====================

class TestGetLlmSentiment:
    def test_uses_cache(self):
        _llm_cache["test_hash"] = {"sentiment_score": 0.5}
        # Different text but we'll verify cache miss path
        with patch("src.llm.news_sentiment._call_llm_with_failover") as m:
            m.return_value = {"sentiment_score": 0.7}
            result = get_llm_sentiment("new text")
        assert result["sentiment_score"] == 0.7
        # Second call with same text uses cache
        result2 = get_llm_sentiment("new text")
        assert result2["sentiment_score"] == 0.7

    def test_fallback_on_error(self):
        with patch("src.llm.news_sentiment._call_llm_with_failover", side_effect=RuntimeError("boom")):
            result = get_llm_sentiment("test")
        assert result["used_fallback"] is True


# ===================== process_news_with_llm =====================

class TestProcessNewsWithLlm:
    def test_empty_df(self):
        result = process_news_with_llm(pd.DataFrame())
        assert result.empty

    def test_processes_rows(self):
        df = pd.DataFrame([
            {"timestamp": "2025-01-01", "name": "GDP", "country": "US",
             "currency": "USD", "impact_num": 3, "signal": "bullish",
             "event_type": "gdp", "actual": "3.0%", "forecast": "2.5%", "previous": "2.0%"},
        ])
        with patch("src.llm.news_sentiment.get_llm_sentiment") as m:
            m.return_value = {
                "sentiment_score": 0.8, "confidence": 0.9,
                "event_type": "gdp", "volatility_impact": 0.7,
                "reasoning_short": "strong gdp",
                "used_fallback": False, "llm_backend": "primary",
            }
            result = process_news_with_llm(df)
        assert len(result) == 1
        assert result.iloc[0]["sentiment_score"] == 0.8

    def test_shutdown_event_aborts(self):
        df = pd.DataFrame([
            {"timestamp": "2025-01-01", "name": "Test", "country": "US",
             "currency": "USD"},
        ])
        shutdown_event.set()
        with pytest.raises(LLMShutdown):
            process_news_with_llm(df)

    def test_all_backends_cooldown_uses_fallback(self):
        df = pd.DataFrame([
            {"timestamp": "2025-01-01", "name": "Test"},
        ])
        with patch("src.llm.news_sentiment._all_backends_in_cooldown", return_value=True):
            result = process_news_with_llm(df)
        assert result.iloc[0]["used_fallback"] == True


# ===================== save/load_llm_features =====================

class TestSaveLoadLlmFeatures:
    def test_save_and_load(self, fake_project):
        df = pd.DataFrame([
            {"timestamp": pd.Timestamp("2025-01-01"), "name": "Test", "country": "US",
             "sentiment_score": 0.5},
        ])
        save_llm_features(df)
        loaded = load_llm_features()
        assert len(loaded) == 1
        assert loaded.iloc[0]["sentiment_score"] == 0.5

    def test_append_dedup(self, fake_project):
        df1 = pd.DataFrame([{"timestamp": pd.Timestamp("2025-01-01"), "name": "A", "country": "US", "score": 1}])
        df2 = pd.DataFrame([{"timestamp": pd.Timestamp("2025-01-01"), "name": "A", "country": "US", "score": 2}])
        save_llm_features(df1)
        save_llm_features(df2)
        loaded = load_llm_features()
        # Deduplicated: only latest (score=2)
        assert len(loaded) == 1

    def test_load_missing_returns_empty(self, fake_project):
        assert load_llm_features().empty
