@echo off
cd /d C:\Users\Tiago\Documents\repos\Testes\autotrader

:: Backend
start "" cmd /k "cd command_center/backend && call ../../venv/Scripts/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: Frontend
start "" cmd /k "cd command_center/frontend && npm run dev"

:: Loop ML
start "" cmd /k "call venv/Scripts/activate && python -m src.execution.loop"