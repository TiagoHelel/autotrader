"""
Sistema de logging persistente.
Salva logs em CSV para analise posterior.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path

from config.settings import settings


class CSVLogHandler(logging.Handler):
    """Handler que salva logs em arquivo CSV."""

    def __init__(self, filename: str = "system.csv"):
        super().__init__()
        self.log_dir = settings.logs_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.log_dir / filename
        self._ensure_header()

    def _ensure_header(self):
        if not self.filepath.exists():
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "level", "module", "message"])

    def emit(self, record):
        try:
            with open(self.filepath, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    record.levelname,
                    record.name,
                    self.format(record),
                ])
        except Exception:
            self.handleError(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Configura logging para console + CSV."""
    root = logging.getLogger()
    root.setLevel(level)

    # Limpa handlers existentes
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(console)

    # CSV handler
    csv_handler = CSVLogHandler()
    csv_handler.setLevel(level)
    csv_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(csv_handler)


def log_prediction(symbol: str, model: str, predictions: dict, current_price: float):
    """Log de previsao em CSV dedicado."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / "predictions.csv"

    header_needed = not filepath.exists()
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow([
                "timestamp", "symbol", "model", "current_price",
                "pred_t1", "pred_t2", "pred_t3",
            ])
        writer.writerow([
            datetime.utcnow().isoformat(),
            symbol, model, current_price,
            predictions.get("t1"), predictions.get("t2"), predictions.get("t3"),
        ])


def log_decision(symbol: str, action: str, details: str):
    """Log de decisao em CSV dedicado."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / "decisions.csv"

    header_needed = not filepath.exists()
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(["timestamp", "symbol", "action", "details"])
        writer.writerow([
            datetime.utcnow().isoformat(), symbol, action, details,
        ])


def log_signal(symbol: str, model: str, signal: str, confidence: float, expected_return: float):
    """Log de sinal gerado em CSV dedicado."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / "signals.csv"

    header_needed = not filepath.exists()
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow([
                "timestamp", "symbol", "model", "signal",
                "confidence", "expected_return",
            ])
        writer.writerow([
            datetime.utcnow().isoformat(),
            symbol, model, signal, confidence, expected_return,
        ])


def log_session_metrics(
    symbol: str, session: str, session_score: float,
    signal: str, model: str, confidence: float,
):
    """Log de metricas por sessao em CSV dedicado."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / "session_metrics.csv"

    header_needed = not filepath.exists()
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow([
                "timestamp", "symbol", "session", "session_score",
                "signal", "model", "confidence",
            ])
        writer.writerow([
            datetime.utcnow().isoformat(),
            symbol, session, session_score,
            signal, model, confidence,
        ])


def log_backtest_trade(
    symbol: str, model: str, direction: str,
    entry_price: float, exit_price: float, pnl_pips: float,
):
    """Log de trade simulado de backtest."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    filepath = log_dir / "backtest_trades.csv"

    header_needed = not filepath.exists()
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow([
                "timestamp", "symbol", "model", "direction",
                "entry_price", "exit_price", "pnl_pips",
            ])
        writer.writerow([
            datetime.utcnow().isoformat(),
            symbol, model, direction,
            entry_price, exit_price, pnl_pips,
        ])
