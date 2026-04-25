"""
In-process scheduler para os jobs diarios do AutoTrader.

Jobs agendados (UTC):
    01:00  upload_to_s3.py        — sobe S3 + arquiva candles localmente
    02:00  run_daily_eval.py      — cruza pred vs real, atualiza vault
    03:00  run_agent_researcher.py — pesquisa autonoma pos daily_eval

Por que UTC e nao TZ local:
    Mercado FX opera em UTC. Cron diario por TZ local quebra em troca de horario
    de verao. Manter UTC alinha com session.py, candles e analises.

Por que 1h de gap entre os jobs:
    Uploader pode demorar (rede, S3 ETag check em N arquivos). Eval depende dos
    candles arquivados pelo uploader. 1h e folga generosa. O agent researcher
    roda 1h apos o eval para consumir o relatorio/dataset diario ja fechado.

LIMITACAO IMPORTANTE:
    Esta lib (`schedule`) eh IN-PROCESS. Se este script morrer (reboot, crash,
    Ctrl+C, sessao SSH fechada), os jobs param. Para producao real:

    - Windows: Task Scheduler chamando run_daily_eval.py / upload_to_s3.py
      diretamente (sobrevive reboot).
    - Linux: cron / systemd timer.
    - Solucao intermediaria no Windows: rodar este scheduler.py via NSSM
      (transforma em servico que reinicia sozinho).

    O scheduler.py e otimo para dev/teste e para uma maquina sempre-ligada.
    Nao confie nele pra produtos com SLA.

Uso:
    python scripts/scheduler.py                 # roda em foreground
    python scripts/scheduler.py --run-once eval # roda 1 job ad-hoc e sai
    python scripts/scheduler.py --dry-run       # mostra cronograma e sai
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable  # usa o python do venv ativo

logger = logging.getLogger("scheduler")


# =====================================================================
# Job runners
# =====================================================================

def _run(label: str, args: list[str]) -> None:
    """Executa um script como subprocess. Isola crashes do scheduler."""
    started = datetime.now(timezone.utc)
    logger.info(f"[{label}] start at {started.isoformat()} UTC")
    try:
        result = subprocess.run(
            [PY, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60 * 30,  # 30 min
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        if result.returncode == 0:
            logger.info(f"[{label}] OK in {elapsed:.1f}s")
        else:
            logger.error(f"[{label}] FAILED rc={result.returncode} in {elapsed:.1f}s")
            logger.error(f"[{label}] stderr (tail):\n{result.stderr[-2000:]}")
    except subprocess.TimeoutExpired:
        logger.error(f"[{label}] TIMEOUT depois de 30min — abortado")
    except Exception as e:
        logger.exception(f"[{label}] EXCEPTION: {e}")


def job_upload_s3() -> None:
    _run("upload_s3", [str(ROOT / "scripts" / "upload_to_s3.py")])


def job_daily_eval() -> None:
    # Sem --date: usa ontem UTC, que jah esta fechado
    _run("daily_eval", [str(ROOT / "scripts" / "run_daily_eval.py")])


def job_agent_researcher() -> None:
    _run(
        "agent_researcher",
        [str(ROOT / "scripts" / "run_agent_researcher.py")],
    )


JOBS = {
    "upload": (job_upload_s3, "01:00", "Upload S3 + archive local"),
    "eval": (job_daily_eval, "02:00", "Daily eval (pred vs real, vault update)"),
    "agent": (
        job_agent_researcher,
        "03:00",
        "Agent researcher (LLM hypotheses + holdout-safe validation)",
    ),
}


# =====================================================================
# Setup
# =====================================================================

def utc_to_local_hhmm(utc_hhmm: str) -> str:
    """Converte HH:MM em UTC para HH:MM no fuso local da maquina.
    A lib `schedule` so opera em horario local, entao registramos o equivalente."""
    h, m = map(int, utc_hhmm.split(":"))
    today = datetime.now(timezone.utc).date()
    utc_dt = datetime(today.year, today.month, today.day, h, m, tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone()  # tz local da maquina
    return f"{local_dt.hour:02d}:{local_dt.minute:02d}"


def setup_schedule() -> None:
    logger.info(f"TZ local detectada: offset {datetime.now().astimezone().utcoffset()}")
    for name, (fn, when_utc, desc) in JOBS.items():
        when_local = utc_to_local_hhmm(when_utc)
        schedule.every().day.at(when_local).do(fn)
        logger.info(f"  agendado: {name} @ {when_utc} UTC = {when_local} local ({desc})")


def print_dry_run() -> None:
    print("Cronograma agendado (UTC):\n")
    for name, (_, when_utc, desc) in JOBS.items():
        print(f"  {when_utc}  {name:<10}  {desc}")
    print("\nProximas execucoes:")
    for j in schedule.jobs:
        print(f"  {j.next_run}  {j.job_func}")


# =====================================================================
# Entry point
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", choices=list(JOBS.keys()),
                        help="Roda um job ad-hoc e sai (ignora horario)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra cronograma e sai sem executar")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.run_once:
        fn, when, desc = JOBS[args.run_once]
        logger.info(f"Run-once: {args.run_once} ({desc})")
        fn()
        return

    setup_schedule()

    if args.dry_run:
        print_dry_run()
        return

    logger.info(f"Scheduler iniciado. {len(schedule.jobs)} jobs registrados.")
    logger.info("Ctrl+C para parar.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuario.")


if __name__ == "__main__":
    main()
