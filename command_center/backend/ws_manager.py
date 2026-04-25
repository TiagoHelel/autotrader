"""
AutoTrader Command Center - WebSocket Connection Manager
Broadcasts live price ticks, KPI updates, and real log entries to connected clients.

Logs are drip-fed at 0.5s intervals to avoid spamming the frontend.
Reads from real CSV log files produced by the prediction engine.
"""

import asyncio
import csv
import json
import random
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import WebSocket

from database import PIP_SIZE, get_conn

# Log files to watch (relative to project data/logs/)
LOG_FILES = {
    "system": "system.csv",
    "prediction": "predictions.csv",
    "decision": "decisions.csv",
    "signal": "signals.csv",
    "session": "session_metrics.csv",
    "backtest": "backtest_trades.csv",
}


def _get_logs_dir() -> Path:
    """Resolve data/logs/ dir relative to project root."""
    # ws_manager.py is at command_center/backend/
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "logs"


class WSManager:
    """Manages WebSocket connections and periodic data broadcasts."""

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._log_task: asyncio.Task | None = None
        # Track file positions for tailing
        self._file_positions: dict[str, int] = {}
        # Queue of log entries to drip-feed
        self._log_queue: deque[dict[str, Any]] = deque(maxlen=500)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    # ------------------------------------------------------------------ ticks
    def _generate_tick(self) -> dict[str, Any]:
        """Simulate small price movements on open positions and update DB."""
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM positions").fetchall()
            updated_positions = []
            total_pnl = 0.0

            for row in rows:
                symbol = row["symbol"]
                pip = PIP_SIZE[symbol]
                decimals = 5 if pip < 0.001 else 3 if pip < 0.1 else 2

                # Small random move
                move = random.gauss(0, 3) * pip
                new_price = round(row["current_price"] + move, decimals)

                if row["type"] == "BUY":
                    pnl = round((new_price - row["open_price"]) / pip * row["volume"] * 10, 2)
                else:
                    pnl = round((row["open_price"] - new_price) / pip * row["volume"] * 10, 2)

                conn.execute(
                    "UPDATE positions SET current_price = ?, pnl = ? WHERE id = ?",
                    (new_price, pnl, row["id"]),
                )
                total_pnl += pnl
                updated_positions.append({
                    "id": row["id"],
                    "symbol": symbol,
                    "type": row["type"],
                    "volume": row["volume"],
                    "open_price": row["open_price"],
                    "current_price": new_price,
                    "sl": row["sl"],
                    "tp": row["tp"],
                    "pnl": pnl,
                    "open_time": row["open_time"],
                })

            # Update equity in account_state
            account = conn.execute("SELECT * FROM account_state ORDER BY id DESC LIMIT 1").fetchone()
            if account:
                new_equity = round(account["balance"] + total_pnl, 2)
                conn.execute(
                    "UPDATE account_state SET equity = ?, pnl_daily = ? WHERE id = ?",
                    (new_equity, round(total_pnl, 2), account["id"]),
                )

            conn.commit()
            return {
                "positions": updated_positions,
                "equity": new_equity if account else 10245.30,
                "pnl_total": round(total_pnl, 2),
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------ KPIs
    def _get_kpis(self) -> dict[str, Any]:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM account_state ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {}
            return {
                "balance": row["balance"],
                "equity": row["equity"],
                "pnl_daily": row["pnl_daily"],
                "pnl_total": row["pnl_total"],
                "drawdown": row["drawdown"],
                "winrate": row["winrate"],
            }
        finally:
            conn.close()

    # ----------------------------------------------------------- real log tailing
    def _tail_log_files(self) -> list[dict[str, Any]]:
        """
        Read new lines from all CSV log files since last check.
        Returns list of parsed log entries.
        """
        logs_dir = _get_logs_dir()
        if not logs_dir.exists():
            return []

        new_entries = []

        for log_type, filename in LOG_FILES.items():
            filepath = logs_dir / filename
            if not filepath.exists():
                continue

            # Get current file size
            try:
                file_size = filepath.stat().st_size
            except OSError:
                continue

            last_pos = self._file_positions.get(filename, 0)

            # On first run, seek to near end to avoid dumping entire history
            if filename not in self._file_positions:
                # Start from last 2KB or beginning
                self._file_positions[filename] = max(0, file_size - 2048)
                last_pos = self._file_positions[filename]

            # No new data
            if file_size <= last_pos:
                continue

            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_pos)

                    # If we seeked mid-line, skip partial line
                    if last_pos > 0:
                        f.readline()

                    reader = csv.DictReader(f, fieldnames=self._get_fieldnames(log_type))
                    for row in reader:
                        if not row or not any(row.values()):
                            continue
                        # Skip header rows
                        ts = row.get("timestamp", "")
                        if ts == "timestamp" or not ts:
                            continue

                        entry = self._format_log_entry(log_type, row)
                        if entry:
                            new_entries.append(entry)

                    self._file_positions[filename] = f.tell()

            except Exception:
                # File might be locked by writer, skip this cycle
                pass

        # Sort by timestamp
        new_entries.sort(key=lambda x: x.get("timestamp", ""))
        return new_entries

    def _get_fieldnames(self, log_type: str) -> list[str]:
        """Return CSV column names for each log type."""
        if log_type == "system":
            return ["timestamp", "level", "module", "message"]
        elif log_type == "prediction":
            return ["timestamp", "symbol", "model", "current_price", "pred_t1", "pred_t2", "pred_t3"]
        elif log_type == "decision":
            return ["timestamp", "symbol", "action", "details"]
        elif log_type == "signal":
            return ["timestamp", "symbol", "model", "signal", "confidence", "expected_return"]
        elif log_type == "session":
            return ["timestamp", "symbol", "session", "session_score", "signal", "model", "confidence"]
        elif log_type == "backtest":
            return ["timestamp", "symbol", "model", "direction", "entry_price", "exit_price", "pnl_pips"]
        return ["timestamp", "message"]

    def _format_log_entry(self, log_type: str, row: dict) -> dict[str, Any] | None:
        """Format a raw CSV row into a WebSocket log entry."""
        ts = row.get("timestamp", "")
        symbol = row.get("symbol", "")

        if log_type == "system":
            return {
                "timestamp": ts,
                "level": row.get("level", "INFO"),
                "message": f"{symbol + ': ' if symbol else ''}{row.get('message', '')}",
                "module": row.get("module", ""),
                "log_type": "system",
            }

        elif log_type == "prediction":
            model = row.get("model", "")
            price = row.get("current_price", "")
            t1 = row.get("pred_t1", "")
            t2 = row.get("pred_t2", "")
            t3 = row.get("pred_t3", "")
            return {
                "timestamp": ts,
                "level": "INFO",
                "message": f"{symbol} | {model}: price={price} pred_t1={t1} pred_t2={t2} pred_t3={t3}",
                "symbol": symbol,
                "model": model,
                "log_type": "prediction",
            }

        elif log_type == "decision":
            action = row.get("action", "")
            details = row.get("details", "")
            return {
                "timestamp": ts,
                "level": "INFO",
                "message": f"{symbol}: {action} {details}",
                "symbol": symbol,
                "log_type": "decision",
            }

        elif log_type == "signal":
            model = row.get("model", "")
            sig = row.get("signal", "")
            conf = row.get("confidence", "")
            er = row.get("expected_return", "")
            return {
                "timestamp": ts,
                "level": "INFO",
                "message": f"{symbol} | {model}: signal={sig} conf={conf} er={er}",
                "symbol": symbol,
                "model": model,
                "log_type": "signal",
            }

        elif log_type == "session":
            session = row.get("session", "")
            score = row.get("session_score", "")
            sig = row.get("signal", "")
            return {
                "timestamp": ts,
                "level": "INFO",
                "message": f"{symbol}: session=[{session}] score={score} signal={sig}",
                "symbol": symbol,
                "log_type": "session",
            }

        elif log_type == "backtest":
            model = row.get("model", "")
            direction = row.get("direction", "")
            pnl = row.get("pnl_pips", "")
            return {
                "timestamp": ts,
                "level": "INFO",
                "message": f"{symbol} | {model}: {direction} pnl={pnl} pips",
                "symbol": symbol,
                "model": model,
                "log_type": "trade",
            }

        return None

    # ----------------------------------------------------------- healthcheck
    def _run_healthcheck(self) -> dict[str, Any]:
        """
        Real healthcheck: LLM local, prediction engine, models.
        Checks the single configured LLM endpoint (Qwen 3.5 9B local).
        """
        ts = datetime.now(timezone.utc).isoformat()
        checks = {}
        project_root = Path(__file__).resolve().parent.parent.parent

        # 1. Prediction engine — last log write + last prediction timestamp
        logs_dir = _get_logs_dir()
        engine_status = "unknown"
        last_log_age = None
        last_prediction_ts = None

        if logs_dir.exists():
            # Last log write (any CSV)
            latest_mtime = 0
            for f in logs_dir.iterdir():
                if f.suffix == ".csv":
                    try:
                        mt = f.stat().st_mtime
                        if mt > latest_mtime:
                            latest_mtime = mt
                    except OSError:
                        pass
            if latest_mtime > 0:
                age_s = datetime.now(timezone.utc).timestamp() - latest_mtime
                last_log_age = round(age_s)
                engine_status = "active" if age_s < 600 else "stale"
            else:
                engine_status = "no_logs"

            # Last prediction timestamp (from predictions.csv tail)
            pred_log = logs_dir / "predictions.csv"
            if pred_log.exists():
                try:
                    with open(pred_log, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                        if len(lines) > 1:
                            last_prediction_ts = lines[-1].split(",")[0]
                except Exception:
                    pass
        else:
            engine_status = "no_dir"

        checks["engine"] = engine_status
        checks["engine_last_log_age_s"] = last_log_age
        checks["last_prediction"] = last_prediction_ts

        # 2. Models — features parquet count + predictions parquet count
        features_dir = project_root / "data" / "features"
        pred_dir = project_root / "data" / "predictions"
        model_count = len(list(features_dir.glob("*.parquet"))) if features_dir.exists() else 0
        pred_count = len(list(pred_dir.glob("*.parquet"))) if pred_dir.exists() else 0
        checks["models_trained"] = model_count
        checks["predictions_active"] = pred_count
        checks["models"] = "ok" if model_count > 0 else "no_data"

        # 3. LLM — checa o endpoint local (Qwen 3.5 9B)
        llm_status = "unknown"
        try:
            import sys
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from config.settings import settings as app_settings

            llm_url = app_settings.llm.api_url
            if not llm_url:
                llm_status = "not_configured"
            else:
                try:
                    with httpx.Client(timeout=3.0) as client:
                        r = client.get(f"{llm_url.rstrip('/')}/models")
                        llm_status = "ok" if r.status_code in (200, 401) else f"http_{r.status_code}"
                except httpx.ConnectError:
                    llm_status = "unreachable"
                except httpx.TimeoutException:
                    llm_status = "timeout"
                except Exception:
                    llm_status = "error"
        except Exception:
            llm_status = "config_error"

        checks["llm"] = llm_status

        # 4. Backend (FastAPI) — self-check via /api/predict/system/status
        backend_status = "unknown"
        try:
            with httpx.Client(timeout=3.0) as client:
                r = client.get("http://127.0.0.1:8000/api/predict/system/status")
                if r.status_code == 200:
                    backend_status = "ok"
                else:
                    backend_status = f"http_{r.status_code}"
        except httpx.ConnectError:
            backend_status = "unreachable"
        except httpx.TimeoutException:
            backend_status = "timeout"
        except Exception:
            backend_status = "error"

        checks["backend"] = backend_status

        # Build summary message
        engine_age = f" (last: {last_log_age}s ago)" if last_log_age is not None else ""
        msg = (
            f"Backend: {backend_status.upper()} | "
            f"LLM: {llm_status.upper()} | "
            f"Engine: {engine_status.upper()}{engine_age} | "
            f"Models: {model_count} trained, {pred_count} predicting"
        )

        return {
            "timestamp": ts,
            "level": "INFO",
            "message": msg,
            "log_type": "healthcheck",
            "checks": checks,
        }

    # ----------------------------------------------------------- broadcast loops
    async def _tick_loop(self) -> None:
        """Main loop: ticks + KPIs every 2s, check for new logs every 3s."""
        while self._running:
            if self._clients:
                # Price tick
                tick_data = self._generate_tick()
                await self._broadcast({"type": "tick", "data": tick_data})

                # KPI update
                kpis = self._get_kpis()
                await self._broadcast({"type": "kpi", "data": kpis})

            await asyncio.sleep(2)

    async def _log_collector_loop(self) -> None:
        """Polls CSV files every 3s and queues new entries."""
        while self._running:
            try:
                new_logs = await asyncio.to_thread(self._tail_log_files)
                for entry in new_logs:
                    self._log_queue.append(entry)
            except Exception:
                pass
            await asyncio.sleep(3)

    async def _log_drip_loop(self) -> None:
        """Drip-feeds queued log entries at 0.5s per line."""
        while self._running:
            if self._clients and self._log_queue:
                entry = self._log_queue.popleft()
                await self._broadcast({"type": "log", "data": entry})
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.3)

    async def _healthcheck_loop(self) -> None:
        """Runs real healthcheck every 10s and broadcasts as log + dedicated message."""
        while self._running:
            if self._clients:
                try:
                    hc = await asyncio.to_thread(self._run_healthcheck)
                    await self._broadcast({"type": "healthcheck", "data": hc.get("checks", {})})
                    self._log_queue.append(hc)
                except Exception:
                    pass
            await asyncio.sleep(10)

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        self._log_task = asyncio.create_task(self._log_collector_loop())
        asyncio.create_task(self._log_drip_loop())
        asyncio.create_task(self._healthcheck_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._log_task:
            self._log_task.cancel()
            try:
                await self._log_task
            except asyncio.CancelledError:
                pass


ws_manager = WSManager()
