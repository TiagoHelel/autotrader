"""
Wrapper agendavel do avaliador batch diario.

Esta aqui em `scripts/` porque eh o lugar onde ferramentas de schedule
(cron, Windows Task Scheduler, NSSM, scheduler.py) procuram entry points.

A logica vive em `src/evaluation/daily_eval.py` — este arquivo so passa
argumentos e ajusta defaults pra agendamento (default = ontem UTC, idempotente).

Uso direto:
    python scripts/run_daily_eval.py
    python scripts/run_daily_eval.py --date 2026-04-24
    python scripts/run_daily_eval.py --from 2026-04-20 --to 2026-04-24

Agendamento:
    # Windows Task Scheduler (recomendado pra producao):
    #   action: python.exe
    #   args: C:\path\to\autotrader\scripts\run_daily_eval.py
    #   trigger: daily 02:00 UTC
    #
    # Ou via scripts/scheduler.py (in-process, dev/teste).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.daily_eval import main  # noqa: E402

if __name__ == "__main__":
    main()
