"""
Tests for src/execution/loop.py — loop contínuo e pipeline de notícias.

Estratégia: mock do MT5Connection, time.sleep, e funções de pipeline.
Testa get_next_candle_time, wait_for_next_candle, _run_news_pipeline.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.execution.loop import (
    _run_news_pipeline,
    get_next_candle_time,
    run_forever,
    wait_for_next_candle,
)


# ===================== get_next_candle_time =====================

class TestGetNextCandleTime:
    def test_at_minute_00(self):
        with patch("src.execution.loop.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 0, 30)
            result = get_next_candle_time()
        # Next M5 candle at 12:05:05
        assert result.minute == 5
        assert result.second == 5

    def test_at_minute_03(self):
        with patch("src.execution.loop.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 3, 0)
            result = get_next_candle_time()
        assert result.minute == 5
        assert result.second == 5

    def test_at_minute_57(self):
        with patch("src.execution.loop.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 57, 0)
            result = get_next_candle_time()
        # next_5 = (57//5 + 1)*5 = 60 → rolls to next hour
        assert result.hour == 13
        assert result.minute == 0
        assert result.second == 5

    def test_at_minute_55(self):
        with patch("src.execution.loop.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 55, 0)
            result = get_next_candle_time()
        # next_5 = (55//5 + 1)*5 = 60 → rolls to next hour
        assert result.hour == 13

    def test_margin_of_5_seconds(self):
        with patch("src.execution.loop.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 10, 0)
            result = get_next_candle_time()
        assert result == datetime(2025, 1, 1, 12, 15, 5)


# ===================== wait_for_next_candle =====================

class TestWaitForNextCandle:
    @patch("src.execution.loop.time.sleep")
    def test_sleeps_correct_duration(self, mock_sleep):
        with patch("src.execution.loop.get_next_candle_time") as mock_next:
            mock_next.return_value = datetime(2025, 1, 1, 12, 5, 5)
            with patch("src.execution.loop.datetime") as mock_dt:
                mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 0, 5)
                wait_for_next_candle()
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == pytest.approx(300.0)

    @patch("src.execution.loop.time.sleep")
    def test_no_sleep_when_past_due(self, mock_sleep):
        with patch("src.execution.loop.get_next_candle_time") as mock_next:
            mock_next.return_value = datetime(2025, 1, 1, 12, 0, 0)
            with patch("src.execution.loop.datetime") as mock_dt:
                mock_dt.utcnow.return_value = datetime(2025, 1, 1, 12, 5, 0)
                wait_for_next_candle()
        mock_sleep.assert_not_called()


# ===================== _run_news_pipeline =====================

class TestRunNewsPipeline:
    @patch("src.execution.loop.log_decision")
    @patch("src.execution.loop.save_llm_features")
    @patch("src.execution.loop.process_news_with_llm")
    @patch("src.execution.loop.normalize_news")
    @patch("src.execution.loop.run_news_ingestion")
    def test_full_pipeline(self, mock_ingest, mock_norm, mock_llm, mock_save, mock_log):
        mock_ingest.return_value = pd.DataFrame([{"name": "GDP", "country": "US"}])
        mock_norm.return_value = pd.DataFrame([{"name": "GDP", "country": "US"}])
        mock_llm.return_value = pd.DataFrame([{"name": "GDP", "sentiment": 0.5}])
        _run_news_pipeline()
        mock_ingest.assert_called_once()
        mock_norm.assert_called_once()
        mock_llm.assert_called_once()
        mock_save.assert_called_once()

    @patch("src.execution.loop.run_news_ingestion")
    def test_empty_news(self, mock_ingest):
        mock_ingest.return_value = pd.DataFrame()
        _run_news_pipeline()  # Should not crash

    @patch("src.execution.loop.log_decision")
    @patch("src.execution.loop.normalize_news")
    @patch("src.execution.loop.run_news_ingestion")
    def test_llm_failure_continues(self, mock_ingest, mock_norm, mock_log):
        mock_ingest.return_value = pd.DataFrame([{"name": "Test"}])
        mock_norm.return_value = pd.DataFrame([{"name": "Test"}])
        with patch("src.execution.loop.process_news_with_llm", side_effect=RuntimeError("LLM down")):
            _run_news_pipeline()  # Should not crash

    @patch("src.execution.loop.run_news_ingestion", side_effect=RuntimeError("network"))
    def test_scraping_failure(self, mock_ingest):
        _run_news_pipeline()  # Should not crash

    @patch("src.execution.loop.log_decision")
    @patch("src.execution.loop.save_llm_features")
    @patch("src.execution.loop.process_news_with_llm")
    @patch("src.execution.loop.normalize_news")
    @patch("src.execution.loop.run_news_ingestion")
    def test_llm_empty_result_skips_save(self, mock_ingest, mock_norm, mock_llm,
                                           mock_save, mock_log):
        mock_ingest.return_value = pd.DataFrame([{"name": "x"}])
        mock_norm.return_value = pd.DataFrame([{"name": "x"}])
        mock_llm.return_value = pd.DataFrame()  # empty
        _run_news_pipeline()
        mock_save.assert_not_called()


class TestRunForever:
    def test_keyboard_interrupt_exits_cleanly(self):
        """wait_for_next_candle raises KeyboardInterrupt → clean shutdown."""
        fake_conn_cm = MagicMock()
        fake_conn_cm.__enter__ = MagicMock(return_value=MagicMock())
        fake_conn_cm.__exit__ = MagicMock(return_value=False)

        with patch("src.execution.loop.setup_logging"), \
             patch("src.execution.loop.MT5Connection", return_value=fake_conn_cm), \
             patch("src.execution.loop.validate_symbols", return_value=["EURUSD"]), \
             patch("src.execution.loop.PredictionEngine") as MockEngine, \
             patch("src.execution.loop._run_news_pipeline"), \
             patch("src.execution.loop.wait_for_next_candle", side_effect=KeyboardInterrupt), \
             patch("src.execution.loop.log_decision"):
            MockEngine.return_value.initial_setup = MagicMock()
            # should NOT raise
            run_forever()

    def test_cycle_exception_sleeps_and_continues(self):
        """Exception mid-cycle → logs error, sleeps 30s, then breaks via KeyboardInterrupt."""
        fake_conn_cm = MagicMock()
        fake_conn_cm.__enter__ = MagicMock(return_value=MagicMock())
        fake_conn_cm.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.run_cycle.side_effect = RuntimeError("boom")

        call_count = {"n": 0}
        def wait_side_effect():
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise KeyboardInterrupt
        sleep_calls = []

        with patch("src.execution.loop.setup_logging"), \
             patch("src.execution.loop.MT5Connection", return_value=fake_conn_cm), \
             patch("src.execution.loop.validate_symbols", return_value=["EURUSD"]), \
             patch("src.execution.loop.PredictionEngine", return_value=engine), \
             patch("src.execution.loop._run_news_pipeline"), \
             patch("src.execution.loop.wait_for_next_candle", side_effect=wait_side_effect), \
             patch("src.execution.loop.time.sleep", side_effect=sleep_calls.append), \
             patch("src.execution.loop.log_decision"):
            run_forever()
        assert 30 in sleep_calls

    def test_happy_cycle_then_interrupt(self):
        """Full cycle runs, news refresh triggers, then KeyboardInterrupt."""
        fake_conn_cm = MagicMock()
        fake_conn_cm.__enter__ = MagicMock(return_value=MagicMock())
        fake_conn_cm.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.run_cycle.return_value = {
            "symbols": {"EURUSD": {}},
            "elapsed_seconds": 1.2,
        }

        call_count = {"n": 0}
        def wait_side_effect():
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise KeyboardInterrupt

        # Make news refresh trigger: big prediction_interval default → bypass with monkeypatch
        with patch("src.execution.loop.setup_logging"), \
             patch("src.execution.loop.MT5Connection", return_value=fake_conn_cm), \
             patch("src.execution.loop.validate_symbols", return_value=["EURUSD"]), \
             patch("src.execution.loop.PredictionEngine", return_value=engine), \
             patch("src.execution.loop._run_news_pipeline") as mock_news, \
             patch("src.execution.loop.wait_for_next_candle", side_effect=wait_side_effect), \
             patch("src.execution.loop.settings") as mock_settings, \
             patch("src.execution.loop.log_decision"):
            # force news refresh: interval=0 means always refresh
            mock_settings.prediction_interval = 0
            run_forever()
        # news pipeline called: once at startup, once in the loop
        assert mock_news.call_count >= 2
        assert engine.run_cycle.call_count == 1
