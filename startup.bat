@echo off
cd /d C:\Users\Tiago\Documents\repos\Testes\autotrader

:: Backend
start "" cmd /k "cd command_center/backend && call ../../venv/Scripts/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: MT5 Bridge (HTTP pull p/ outras maquinas consumirem candles/tick/account)
start "AutoTrader MT5 API" cmd /k "call venv/Scripts/activate && python -m mt5_api.main"

:: Frontend
start "" cmd /k "cd command_center/frontend && npm run dev"

:: Loop ML
start "" cmd /k "call venv/Scripts/activate && python -m src.execution.loop"

:: Scheduler (upload S3 @ 01:00 UTC, daily eval @ 02:00 UTC)
start "AutoTrader Scheduler" cmd /k "call venv/Scripts/activate && python scripts/scheduler.py"