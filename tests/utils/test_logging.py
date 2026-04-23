"""Tests for src/utils/logging.py — CSV log handlers + helper writers."""

import csv
import logging
from pathlib import Path

import pytest

from src.utils import logging as mod
from config.settings import settings


@pytest.fixture
def fake_logs_dir(tmp_path, monkeypatch):
    """Redirects settings.logs_dir (a computed property) by setting project_root."""
    monkeypatch.setattr(settings, "project_root", tmp_path)
    logs = tmp_path / "data" / "logs"
    return logs


# ========================= CSVLogHandler =========================

class TestCSVLogHandler:
    def test_creates_log_dir_and_writes_header(self, fake_logs_dir):
        handler = mod.CSVLogHandler(filename="test.csv")
        assert fake_logs_dir.exists()
        assert handler.filepath == fake_logs_dir / "test.csv"
        # Header written on init
        with open(handler.filepath) as f:
            header = next(csv.reader(f))
        assert header == ["timestamp", "level", "module", "message"]

    def test_does_not_rewrite_header_when_file_exists(self, fake_logs_dir):
        # Pre-create file with custom content
        fake_logs_dir.mkdir(parents=True, exist_ok=True)
        existing = fake_logs_dir / "existing.csv"
        existing.write_text("preexisting,data\n1,2\n")

        mod.CSVLogHandler(filename="existing.csv")

        assert existing.read_text().startswith("preexisting,data")

    def test_emit_writes_record_row(self, fake_logs_dir):
        handler = mod.CSVLogHandler(filename="emit.csv")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test.module", level=logging.INFO, pathname="x.py",
            lineno=1, msg="hello world", args=(), exc_info=None,
        )
        handler.emit(record)

        with open(handler.filepath) as f:
            rows = list(csv.reader(f))
        # Header + 1 data row
        assert len(rows) == 2
        _ts, level, name, message = rows[1]
        assert level == "INFO"
        assert name == "test.module"
        assert message == "hello world"

    def test_emit_handles_write_error_via_handleError(self, fake_logs_dir, monkeypatch):
        handler = mod.CSVLogHandler(filename="err.csv")
        handler.setFormatter(logging.Formatter("%(message)s"))

        called = []
        monkeypatch.setattr(handler, "handleError", lambda r: called.append(r))

        # Force open() to raise
        def bad_open(*a, **kw):
            raise OSError("disk full")
        monkeypatch.setattr("builtins.open", bad_open)

        record = logging.LogRecord(
            name="x", level=logging.ERROR, pathname="p",
            lineno=1, msg="m", args=(), exc_info=None,
        )
        handler.emit(record)

        assert called == [record]


# ========================= setup_logging =========================

class TestSetupLogging:
    def test_configures_console_and_csv_handlers(self, fake_logs_dir):
        mod.setup_logging(level=logging.DEBUG)
        root = logging.getLogger()

        assert root.level == logging.DEBUG
        # Should have exactly a StreamHandler and a CSVLogHandler
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "StreamHandler" in handler_types
        assert "CSVLogHandler" in handler_types

        # Cleanup
        root.handlers.clear()

    def test_clears_existing_handlers(self, fake_logs_dir):
        root = logging.getLogger()
        dummy = logging.NullHandler()
        root.addHandler(dummy)

        mod.setup_logging(level=logging.INFO)
        assert dummy not in root.handlers

        root.handlers.clear()


# ========================= log_prediction =========================

class TestLogPrediction:
    def test_writes_header_on_first_call(self, fake_logs_dir):
        mod.log_prediction("EURUSD", "xgb", {"t1": 1.1, "t2": 1.2, "t3": 1.3}, 1.0)
        fp = fake_logs_dir / "predictions.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["timestamp", "symbol", "model", "current_price",
                           "pred_t1", "pred_t2", "pred_t3"]
        assert rows[1][1:] == ["EURUSD", "xgb", "1.0", "1.1", "1.2", "1.3"]

    def test_appends_without_rewriting_header(self, fake_logs_dir):
        mod.log_prediction("EURUSD", "xgb", {"t1": 1.1}, 1.0)
        mod.log_prediction("GBPUSD", "linear", {"t1": 1.2}, 1.0)
        fp = fake_logs_dir / "predictions.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        # header + 2 rows
        assert len(rows) == 3
        assert rows[1][1] == "EURUSD"
        assert rows[2][1] == "GBPUSD"

    def test_missing_keys_become_empty(self, fake_logs_dir):
        mod.log_prediction("EURUSD", "xgb", {}, 1.0)
        fp = fake_logs_dir / "predictions.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        # Dict .get() returns None → csv writes ""
        assert rows[1][4:] == ["", "", ""]


# ========================= log_decision =========================

class TestLogDecision:
    def test_writes_header_and_row(self, fake_logs_dir):
        mod.log_decision("EURUSD", "BUY", "strong signal")
        fp = fake_logs_dir / "decisions.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["timestamp", "symbol", "action", "details"]
        assert rows[1][1:] == ["EURUSD", "BUY", "strong signal"]

    def test_appends_second_row(self, fake_logs_dir):
        mod.log_decision("EURUSD", "BUY", "a")
        mod.log_decision("GBPUSD", "SELL", "b")
        fp = fake_logs_dir / "decisions.csv"
        assert len(fp.read_text().splitlines()) == 3


# ========================= log_signal =========================

class TestLogSignal:
    def test_writes_header_and_row(self, fake_logs_dir):
        mod.log_signal("EURUSD", "xgb", "BUY", 0.85, 0.002)
        fp = fake_logs_dir / "signals.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["timestamp", "symbol", "model", "signal",
                           "confidence", "expected_return"]
        assert rows[1][1:] == ["EURUSD", "xgb", "BUY", "0.85", "0.002"]


# ========================= log_session_metrics =========================

class TestLogSessionMetrics:
    def test_writes_header_and_row(self, fake_logs_dir):
        mod.log_session_metrics("EURUSD", "london", 0.9, "BUY", "xgb", 0.7)
        fp = fake_logs_dir / "session_metrics.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["timestamp", "symbol", "session", "session_score",
                           "signal", "model", "confidence"]
        assert rows[1][1:] == ["EURUSD", "london", "0.9", "BUY", "xgb", "0.7"]


# ========================= log_backtest_trade =========================

class TestLogBacktestTrade:
    def test_writes_header_and_row(self, fake_logs_dir):
        mod.log_backtest_trade("EURUSD", "xgb", "LONG", 1.10, 1.11, 10.0)
        fp = fake_logs_dir / "backtest_trades.csv"
        with open(fp) as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["timestamp", "symbol", "model", "direction",
                           "entry_price", "exit_price", "pnl_pips"]
        assert rows[1][1:] == ["EURUSD", "xgb", "LONG", "1.1", "1.11", "10.0"]

    def test_appends_multiple(self, fake_logs_dir):
        mod.log_backtest_trade("EURUSD", "xgb", "LONG", 1.10, 1.11, 10.0)
        mod.log_backtest_trade("EURUSD", "xgb", "SHORT", 1.10, 1.09, 10.0)
        fp = fake_logs_dir / "backtest_trades.csv"
        assert len(fp.read_text().splitlines()) == 3
