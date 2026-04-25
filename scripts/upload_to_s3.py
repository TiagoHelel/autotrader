"""
Upload incremental dos ativos de dados pro S3, com particionamento Hive.

Estrutura no S3 (prefixo configuravel):
    predictions/symbol=EURUSD/date=2026-04-23/part.parquet
    candles/symbol=EURUSD/date=2026-04-23/part.parquet
    news/date=2026-04-23/raw.parquet
    news_llm/features.parquet
    experiments/date=2026-04-23/runs.parquet

Incremental: cada arquivo local tem seu md5 calculado e comparado com o
ETag do objeto no S3. Se bate, pula. Se nao bate (ou nao existe), faz upload.
  - Particoes de dias passados: sobem uma vez, depois sao skipadas.
  - Particao do dia corrente: re-sobe toda execucao (pequena e eh append-only).
  - Arquivos regeneraveis (features/, backtest/, metrics/, logs/): NAO sobem.

Anti-rotacao (data/archive/):
  Antes de cada upload, a particao eh fundida (UNION + dedupe) com a versao
  ja gravada em data/archive/{base}/symbol=X/date=Y/part.parquet. Isso garante
  que mesmo que o buffer rolante data/raw/ perca dias antigos, eles continuam
  vivos no archive local + S3. Dedup por chaves canonicas (DEDUP_KEYS).

Como rodar:
    python scripts/upload_to_s3.py                # upload
    python scripts/upload_to_s3.py --dry-run      # apenas lista o que faria
    python scripts/upload_to_s3.py --prefix autotrader-dev

Cadencia sugerida:
  - Dev/validacao: manual quando quiser snapshot.
  - Producao: a cada fim de ciclo horario (ou end-of-day) via cron/scheduler.
    O custo de rodar frequentemente eh baixo porque so o dia corrente re-sobe.

Requer env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def s3_etag(client, bucket: str, key: str) -> str | None:
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        return head["ETag"].strip('"')
    except client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def upload_bytes(client, bucket: str, key: str, data: bytes, dry_run: bool) -> str:
    local_md5 = md5_bytes(data)
    remote = s3_etag(client, bucket, key)
    if remote == local_md5:
        return "skip"
    if dry_run:
        return "would-upload"
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/octet-stream")
    return "upload"


def split_by_date(df: pd.DataFrame, date_col: str) -> dict[str, pd.DataFrame]:
    ts = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    dates = ts.dt.strftime("%Y-%m-%d")
    out: dict[str, pd.DataFrame] = {}
    for d, sub in df.groupby(dates, sort=True):
        if pd.isna(d) or d == "NaT":
            continue
        out[d] = sub.drop(columns=[]).reset_index(drop=True)
    return out


def archive_path(archive_root: Path, base: str, symbol: str | None, date: str) -> Path:
    parts = [archive_root, base]
    if symbol:
        parts.append(f"symbol={symbol}")
    parts.append(f"date={date}")
    out_dir = Path(*[str(p) for p in parts])
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "part.parquet"


def archive_merge(out_path: Path, new_df: pd.DataFrame, dedup_cols: list[str]) -> pd.DataFrame:
    """Faz UNION do que ja esta no archive com o novo df e deduplica.
    Garante que o archive nunca regrida quando o buffer rolante perder dados antigos."""
    if out_path.exists():
        try:
            existing = pd.read_parquet(out_path)
            combined = pd.concat([existing, new_df], ignore_index=True)
        except Exception:
            combined = new_df
    else:
        combined = new_df
    if dedup_cols and all(c in combined.columns for c in dedup_cols):
        combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
    return combined.reset_index(drop=True)


# dedup keys por dataset — define o que e "mesma linha" pra evitar duplicacao
DEDUP_KEYS = {
    "candles": ["time"],
    "predictions": ["timestamp", "model"],
    "experiments": ["timestamp", "symbol", "model"],
}


def upload_partitioned(client, bucket, prefix, base, files, date_col, symbol_in_path,
                       dry_run, log, archive_root: Path | None = None):
    dedup = DEDUP_KEYS.get(base, [])
    for path in files:
        df = pd.read_parquet(path)
        if df.empty or date_col not in path_columns(df, date_col):
            continue
        symbol = path.stem if symbol_in_path else None
        for date, sub in split_by_date(df, date_col).items():
            # 1. Merge com archive existente (UNION + dedupe) — protege contra rotacao
            if archive_root is not None:
                arch_path = archive_path(archive_root, base, symbol, date)
                merged = archive_merge(arch_path, sub, dedup)
                data = parquet_bytes(merged)
                arch_path.write_bytes(data)
                rows = len(merged)
            else:
                data = parquet_bytes(sub)
                rows = len(sub)

            # 2. Upload incremental pro S3 (md5 vs ETag)
            parts = [prefix, base]
            if symbol:
                parts.append(f"symbol={symbol}")
            parts.append(f"date={date}")
            parts.append("part.parquet")
            key = "/".join(p.strip("/") for p in parts if p)
            status = upload_bytes(client, bucket, key, data, dry_run)
            log.append((status, key, rows))


def path_columns(df: pd.DataFrame, col: str) -> list:
    return list(df.columns) if col in df.columns else []


def upload_agent_researcher(client, bucket, prefix, dry_run, log) -> None:
    """Upload runtime artifacts of the autonomous research agent.

    Layout in the bucket::

        agent_researcher/state/state-YYYY-MM-DD.json    # daily snapshot
        agent_researcher/strategies/active/<id>.json
        agent_researcher/strategies/rejected/<id>.json
        agent_researcher/prompts/date=YYYY-MM-DD/<file> # full audit trail

    The snapshot key includes today's UTC date so we never overwrite
    yesterday's holdout-tracking state — losing it would break the
    one-shot holdout discipline.
    """
    base = ROOT / "src" / "agent_researcher"
    state_path = base / "state.json"
    if state_path.exists():
        today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
        upload_single(
            client, bucket, prefix,
            f"agent_researcher/state/state-{today}.json",
            state_path, dry_run, log,
        )

    for sub in ("active", "rejected"):
        for path in sorted((base / "strategies" / sub).glob("*.json")):
            upload_single(
                client, bucket, prefix,
                f"agent_researcher/strategies/{sub}/{path.name}",
                path, dry_run, log,
            )

    prompts_dir = base / "tmp" / "prompts"
    if prompts_dir.exists():
        for path in sorted(prompts_dir.glob("*")):
            if not path.is_file():
                continue
            date = pd.Timestamp.utcfromtimestamp(path.stat().st_mtime)
            date_str = date.strftime("%Y-%m-%d")
            upload_single(
                client, bucket, prefix,
                f"agent_researcher/prompts/date={date_str}/{path.name}",
                path, dry_run, log,
            )


def upload_single(client, bucket, prefix, key_suffix, path, dry_run, log):
    if not path.exists():
        return
    data = path.read_bytes()
    key = "/".join(p.strip("/") for p in [prefix, key_suffix] if p)
    status = upload_bytes(client, bucket, key, data, dry_run)
    log.append((status, key, None))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prefix", default="", help="Prefixo dentro do bucket (ex: autotrader-dev)")
    args = parser.parse_args()

    import boto3

    s3_cfg = settings.s3
    if not s3_cfg.bucket:
        print("ERRO: S3_BUCKET nao configurado no .env")
        sys.exit(1)

    client = boto3.client(
        "s3",
        aws_access_key_id=s3_cfg.access_key_id or None,
        aws_secret_access_key=s3_cfg.secret_access_key or None,
        region_name=s3_cfg.region,
    )
    bucket = s3_cfg.bucket
    prefix = args.prefix.strip("/")
    data_dir = settings.data_dir

    # Espelho local imutavel — protege contra rotacao do buffer raw/
    # (raw/ guarda apenas as ultimas N barras; sem archive, dias antigos somem)
    archive_root = data_dir / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)

    log: list[tuple[str, str, int | None]] = []

    upload_partitioned(
        client, bucket, prefix, "predictions",
        sorted((data_dir / "predictions").glob("*.parquet")),
        date_col="timestamp", symbol_in_path=True,
        dry_run=args.dry_run, log=log,
        archive_root=archive_root,
    )

    upload_partitioned(
        client, bucket, prefix, "candles",
        sorted((data_dir / "raw").glob("*.parquet")),
        date_col="time", symbol_in_path=True,
        dry_run=args.dry_run, log=log,
        archive_root=archive_root,
    )

    upload_partitioned(
        client, bucket, prefix, "experiments",
        [data_dir / "experiments" / "experiments.parquet"],
        date_col="timestamp", symbol_in_path=False,
        dry_run=args.dry_run, log=log,
        archive_root=archive_root,
    )

    for news_file in sorted((data_dir / "news").glob("raw_*.parquet")):
        date = news_file.stem.replace("raw_", "")
        upload_single(client, bucket, prefix, f"news/date={date}/raw.parquet", news_file, args.dry_run, log)

    upload_single(client, bucket, prefix, "news_llm/features.parquet",
                  data_dir / "news" / "llm_features.parquet", args.dry_run, log)

    upload_agent_researcher(client, bucket, prefix, args.dry_run, log)

    counts = {"upload": 0, "skip": 0, "would-upload": 0}
    for status, key, rows in log:
        counts[status] = counts.get(status, 0) + 1
        if status != "skip":
            rows_s = f" rows={rows}" if rows is not None else ""
            print(f"  [{status}] s3://{bucket}/{key}{rows_s}")

    print(
        f"\nTotal: upload={counts.get('upload', 0)} "
        f"skip={counts.get('skip', 0)} "
        f"would-upload={counts.get('would-upload', 0)}"
    )


if __name__ == "__main__":
    main()
