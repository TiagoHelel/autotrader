import pytest

from src.agent_researcher.llm_interface import (
    LLMCallError,
    _needs_cmd_wrapper,
    parse_hypotheses_json,
)


def test_parse_hypotheses_json_accepts_structured_array():
    text = """
    [
      {
        "hypothesis": "XAUUSD high confidence works in NY",
        "filters": {"symbol": "XAUUSD", "confidence_min": 0.85},
        "reasoning": "Liquidity concentrates during NY flow.",
        "expected_behavior": "Higher hit rate with enough samples."
      }
    ]
    """

    hypotheses = parse_hypotheses_json(text)

    assert len(hypotheses) == 1
    assert hypotheses[0].filters["symbol"] == "XAUUSD"


def test_parse_hypotheses_json_rejects_missing_json():
    with pytest.raises(LLMCallError):
        parse_hypotheses_json("not json")


def test_windows_cmd_shims_need_cmd_wrapper():
    assert _needs_cmd_wrapper("C:/tools/opencode.cmd", "opencode")
    assert _needs_cmd_wrapper(None, "opencode")
    assert not _needs_cmd_wrapper("C:/tools/opencode.exe", "opencode")


def test_opencode_client_call_returns_stdout(monkeypatch):
    from unittest.mock import MagicMock, patch
    import subprocess

    from src.agent_researcher.llm_interface import OpenCodeClient

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "raw llm output"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        client = OpenCodeClient(command="opencode")
        output = client.call("test prompt")

    assert output == "raw llm output"


def test_opencode_client_call_raises_on_nonzero_exit(monkeypatch):
    from unittest.mock import MagicMock, patch

    from src.agent_researcher.llm_interface import LLMCallError, OpenCodeClient

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "something failed"

    with patch("subprocess.run", return_value=mock_result):
        client = OpenCodeClient(command="opencode")
        with pytest.raises(LLMCallError):
            client.call("test prompt")
