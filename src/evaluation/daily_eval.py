"""
Avaliador batch diario (camada 1 do avaliador automatico).

Cruza predicoes do dia com candles reais (t+5/10/15min), segmenta por
contexto (model, symbol, session, regime, confidence) e gera relatorio
markdown em vault/Research/eval-daily/. Tambem:

  1. Arquiva candles localmente em data/archive/candles/symbol=X/date=Y/
     (UNION + dedup) — protege contra rotacao do buffer raw/.
  2. Compara hit rate hoje vs media rolling 30d -> dispara drift flags.
  3. Roda hipoteses ativas em vault/Hypotheses/*.md com `filters` no
     YAML frontmatter, atualiza a nota com resultado.
  4. Salva dataset enriquecido em data/research/eval_{date}.parquet.

Uso:
    python -m src.evaluation.daily_eval                              # ontem (UTC)
    python -m src.evaluation.daily_eval --date 2026-04-24
    python -m src.evaluation.daily_eval --from 2026-04-20 --to 2026-04-24
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
VAULT_DIR = ROOT / "vault"
HYPOTHESES_DIR = VAULT_DIR / "Hypotheses"
EVAL_DAILY_DIR = VAULT_DIR / "Research" / "eval-daily"

HORIZONS_MIN = [5, 10, 15]  # M5: t+1, t+2, t+3 candles a frente


# =====================================================================
# Archive local de candles (anti-rotacao do buffer raw/)
# =====================================================================

def archive_candles_for_date(date: str, candles: pd.DataFrame, symbol: str) -> Path:
    """UNION + dedup com archive existente. Append-only, idempotente."""
    archive_dir = (settings.data_dir / "archive" / "candles" /
                   f"symbol={symbol}" / f"date={date}")
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_path = archive_dir / "part.parquet"

    if out_path.exists():
        existing = pd.read_parquet(out_path)
        combined = pd.concat([existing, candles], ignore_index=True)
        combined = combined.drop_duplicates(subset=["time"], keep="last")
    else:
        combined = candles.copy()

    combined["time"] = pd.to_datetime(combined["time"])
    combined = combined.sort_values("time").reset_index(drop=True)
    combined.to_parquet(out_path, index=False)
    return out_path


def load_candles_for_dates(symbol: str, dates: list[str]) -> pd.DataFrame:
    """Une archive (preferido) + raw (fallback). Dedup por `time`."""
    parts = []
    archive_root = settings.data_dir / "archive" / "candles" / f"symbol={symbol}"
    for date in dates:
        ap = archive_root / f"date={date}" / "part.parquet"
        if ap.exists():
            parts.append(pd.read_parquet(ap))

    raw_path = settings.data_dir / "raw" / f"{symbol}.parquet"
    if raw_path.exists():
        raw = pd.read_parquet(raw_path)
        raw["time"] = pd.to_datetime(raw["time"])
        for date in dates:
            day = raw[raw["time"].dt.date.astype(str) == date]
            if not day.empty:
                parts.append(day)

    if not parts:
        return pd.DataFrame()

    df = pd.concat(parts, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"])
    df = (df.drop_duplicates(subset=["time"], keep="last")
            .sort_values("time")
            .reset_index(drop=True))
    return df


# =====================================================================
# Match predicao -> candle real
# =====================================================================

def match_predictions_to_actuals(pred: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Para cada pred, busca close do candle M5 fechado em t+h."""
    pred = pred.sort_values("timestamp").reset_index(drop=True)
    for h_idx, h_min in enumerate(HORIZONS_MIN, start=1):
        target = (pred["timestamp"] + pd.Timedelta(minutes=h_min)).dt.ceil("5min")
        m = pd.merge_asof(
            pd.DataFrame({"target_time": target, "_idx": pred.index}).sort_values("target_time"),
            candles[["time", "close"]].rename(columns={"time": "target_time", "close": "actual"}),
            on="target_time", direction="forward",
            tolerance=pd.Timedelta(minutes=5),
        ).set_index("_idx").sort_index()
        pred[f"actual_t{h_idx}"] = m["actual"].values

    for h in [1, 2, 3]:
        pred[f"dir_pred_t{h}"] = np.sign(pred[f"pred_t{h}"] - pred["current_price"])
        pred[f"dir_act_t{h}"]  = np.sign(pred[f"actual_t{h}"] - pred["current_price"])
        pred[f"hit_t{h}"]      = (
            (pred[f"dir_pred_t{h}"] == pred[f"dir_act_t{h}"])
            & (pred[f"dir_act_t{h}"] != 0)
        )
        pred[f"err_abs_t{h}"]  = (pred[f"actual_t{h}"] - pred[f"pred_t{h}"]).abs()
        pred[f"ret_real_t{h}"] = (pred[f"actual_t{h}"] - pred["current_price"]) / pred["current_price"]
    return pred


# =====================================================================
# Aggregations
# =====================================================================

def _safe_groupby(df: pd.DataFrame, by, **agg) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return df.groupby(by, observed=True, dropna=False).agg(**agg).round(4).reset_index()


def aggregate_metrics(matched: pd.DataFrame) -> dict:
    nonzero = matched[matched["dir_act_t1"] != 0]
    out: dict = {
        "n_total": len(matched),
        "n_with_movement": len(nonzero),
    }

    out["by_model"] = _safe_groupby(
        nonzero, "model",
        hit_t1=("hit_t1", "mean"),
        hit_t2=("hit_t2", "mean"),
        hit_t3=("hit_t3", "mean"),
        n=("hit_t1", "count"),
    ).sort_values("hit_t1", ascending=False)

    out["by_symbol_model"] = _safe_groupby(
        nonzero, ["symbol", "model"],
        hit=("hit_t1", "mean"),
        n=("hit_t1", "count"),
    ).sort_values("hit", ascending=False)

    out["by_session"] = _safe_groupby(
        nonzero, "session",
        hit=("hit_t1", "mean"),
        n=("hit_t1", "count"),
    ).sort_values("hit", ascending=False)

    out["by_regime"] = {
        col: _safe_groupby(nonzero, col, hit=("hit_t1", "mean"), n=("hit_t1", "count"))
        for col in ["regime_trend", "regime_vol", "regime_range"]
    }

    out["by_signal"] = _safe_groupby(
        nonzero, "signal",
        hit=("hit_t1", "mean"),
        n=("hit_t1", "count"),
    )

    if not nonzero.empty and "confidence" in nonzero.columns:
        df = nonzero.copy()
        df["conf_bin"] = pd.cut(
            df["confidence"].astype(float),
            bins=[0, 0.3, 0.5, 0.7, 0.85, 1.01],
            labels=["<0.3", "0.3-0.5", "0.5-0.7", "0.7-0.85", "0.85+"],
        )
        out["by_confidence"] = _safe_groupby(
            df, "conf_bin",
            hit=("hit_t1", "mean"),
            n=("hit_t1", "count"),
        )
    else:
        out["by_confidence"] = pd.DataFrame()

    trades = nonzero[nonzero["signal"].isin(["BUY", "SELL"])].copy()
    if not trades.empty:
        trades["pnl_pct"] = np.where(
            trades["signal"] == "BUY",
            trades["ret_real_t1"],
            -trades["ret_real_t1"],
        )
        out["pnl_by_model"] = trades.groupby("model").agg(
            n=("pnl_pct", "count"),
            pnl_bps=("pnl_pct", lambda x: x.mean() * 1e4),
            winrate=("pnl_pct", lambda x: (x > 0).mean()),
        ).round(4).reset_index().sort_values("pnl_bps", ascending=False)
    else:
        out["pnl_by_model"] = pd.DataFrame()

    return out


# =====================================================================
# Drift detection (vs baseline rolling 30d)
# =====================================================================

def load_baseline_evals(end_date: str, days: int = 30) -> pd.DataFrame:
    research_dir = settings.data_dir / "research"
    if not research_dir.exists():
        return pd.DataFrame()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    parts = []
    for i in range(1, days + 1):
        d = (end - timedelta(days=i)).isoformat()
        p = research_dir / f"eval_{d}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def detect_drift(today_metrics: dict, baseline: pd.DataFrame, threshold_pp: float = 10.0) -> list[dict]:
    flags = []
    if baseline.empty or today_metrics["by_model"].empty:
        return flags
    nonzero_b = baseline[baseline["dir_act_t1"] != 0]
    if nonzero_b.empty:
        return flags
    base_by_model = nonzero_b.groupby("model")["hit_t1"].mean()
    for _, row in today_metrics["by_model"].iterrows():
        model = row["model"]
        today_hit = row["hit_t1"]
        if model in base_by_model.index:
            base_hit = base_by_model[model]
            delta_pp = (today_hit - base_hit) * 100
            if abs(delta_pp) > threshold_pp:
                flags.append({
                    "type": "model_drift",
                    "model": model,
                    "today": float(today_hit),
                    "baseline": float(base_hit),
                    "delta_pp": float(delta_pp),
                })
    return flags


# =====================================================================
# Auto-run hipoteses (vault/Hypotheses/*.md com `filters` no frontmatter)
# =====================================================================

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter simples. Retorna (meta, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    current_dict = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and current_dict is not None:
            k, _, v = line.strip().partition(":")
            current_dict[k.strip()] = _coerce(v.strip())
        else:
            k, _, v = line.partition(":")
            v = v.strip()
            if v == "":
                current_dict = {}
                meta[k.strip()] = current_dict
            else:
                current_dict = None
                meta[k.strip()] = _coerce(v)
    return meta, body


def _coerce(v: str):
    if v.startswith("[") and v.endswith("]"):
        return [s.strip().strip("'\"") for s in v[1:-1].split(",") if s.strip()]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v.strip("'\"")


def apply_filter(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df
    for k, v in (filters or {}).items():
        if k == "confidence_min" and "confidence" in out.columns:
            out = out[out["confidence"].astype(float) >= float(v)]
        elif k in out.columns:
            if isinstance(v, list):
                out = out[out[k].isin(v)]
            else:
                out = out[out[k] == v]
    return out


def evaluate_hypothesis_on_eval(eval_df: pd.DataFrame, filters: dict) -> dict:
    """Roda filter + computa metricas resumidas. Sem holdout aqui — o holdout
    formal eh feito via `conditional_analysis.evaluate_filter`. Esta funcao
    eh apenas o snapshot diario pra alimentar a tendencia."""
    sub = apply_filter(eval_df, filters)
    nonzero = sub[sub["dir_act_t1"] != 0]
    n = len(nonzero)
    if n == 0:
        return {"n": 0, "verdict": "REJECTED_N"}
    hit = float(nonzero["hit_t1"].mean())
    # Wilson CI95 simplificado
    z = 1.96
    p = hit
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    half = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / den
    ci_low, ci_high = centre - half, centre + half
    # Verdict simplificado
    if n < 30:
        verdict = "UNDERPOWERED"
    elif hit <= 0.50:
        verdict = "REJECTED_WR"
    elif ci_low <= 0.50:
        verdict = "WEAK"
    else:
        verdict = "PROMISING"
    return {
        "n": n,
        "hit_t1": round(hit, 4),
        "ci95_low": round(ci_low, 4),
        "ci95_high": round(ci_high, 4),
        "verdict": verdict,
    }


def update_hypothesis_note(note_path: Path, date: str, result: dict) -> None:
    """Append uma linha de tracking diaria no bloco 'Daily eval log' da nota.
    Nao mexe no bloco 'Resultado' (esse e preenchido manualmente apos
    conditional_analysis.evaluate_filter formal)."""
    text = note_path.read_text(encoding="utf-8")
    log_marker = "## Daily eval log (auto)"
    line = (f"- {date}: n={result['n']} | hit_t1={result.get('hit_t1','-')} "
            f"| CI95=[{result.get('ci95_low','-')}, {result.get('ci95_high','-')}] "
            f"| verdict={result['verdict']}")
    if log_marker not in text:
        # Append section at end
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n{log_marker}\n\n{line}\n"
    else:
        # Insert line at top of section (most recent first)
        idx = text.find(log_marker) + len(log_marker)
        # find end of section header line
        nl = text.find("\n", idx)
        # Avoid duplicating same date
        if f"- {date}:" in text[nl:]:
            # replace existing line
            pattern = re.compile(rf"^- {re.escape(date)}:.*$", re.MULTILINE)
            text = pattern.sub(line, text)
        else:
            text = text[:nl + 1] + "\n" + line + "\n" + text[nl + 1:]
    note_path.write_text(text, encoding="utf-8")


def run_hypotheses_for_eval(eval_df: pd.DataFrame, date: str) -> list[dict]:
    results = []
    if not HYPOTHESES_DIR.exists():
        return results
    for note in sorted(HYPOTHESES_DIR.glob("*.md")):
        if note.stem.startswith("_"):
            continue
        try:
            text = note.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            filters = meta.get("filters")
            if not isinstance(filters, dict) or not filters:
                continue
            res = evaluate_hypothesis_on_eval(eval_df, filters)
            res["hypothesis"] = note.stem
            res["filters"] = filters
            update_hypothesis_note(note, date, res)
            results.append(res)
            logger.info(f"Hipotese {note.stem}: {res}")
        except Exception as e:
            logger.exception(f"Falha ao avaliar hipotese {note.name}: {e}")
    return results


# =====================================================================
# Markdown report
# =====================================================================

def render_report(date: str, metrics: dict, drift: list, baseline_n: int,
                  hypothesis_results: list) -> str:
    lines = [
        "---",
        "type: eval-daily",
        f"date: {date}",
        f"created: {datetime.now(timezone.utc).isoformat()}",
        "tags: [eval-daily, automated]",
        "---",
        "",
        f"# Eval Diaria - {date}",
        "",
        "Gerado automaticamente por `src/evaluation/daily_eval.py`.",
        "",
        f"- N total predicoes (com schema enriquecido): {metrics['n_total']}",
        f"- N com movimento real (denominador hit rate): {metrics['n_with_movement']}",
        (f"- Baseline rolling 30d disponivel: {baseline_n} amostras"
         if baseline_n > 0 else "- Baseline rolling 30d: ainda acumulando"),
        "",
    ]

    if drift:
        lines += ["## Drift flags", ""]
        for f in drift:
            lines.append(
                f"- **{f['model']}**: hoje={f['today']:.3f} vs baseline 30d={f['baseline']:.3f} "
                f"(delta {f['delta_pp']:+.1f}pp) — investigar"
            )
        lines.append("")

    def _md(df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return "_(sem dados)_"
        return df.to_markdown(index=False)

    lines += ["## Hit rate por modelo", "", _md(metrics["by_model"]), ""]
    lines += ["## Hit rate por sessao (t+1)", "", _md(metrics["by_session"]), ""]
    if not metrics["by_confidence"].empty:
        lines += ["## Hit rate por confidence bin", "", _md(metrics["by_confidence"]), ""]
    lines += ["## Hit rate por signal engine", "", _md(metrics["by_signal"]), ""]
    lines += ["## Hit rate por regime", ""]
    for k, df in metrics["by_regime"].items():
        lines += [f"### {k}", "", _md(df), ""]
    if not metrics["pnl_by_model"].empty:
        lines += ["## PnL bruto (BUY/SELL apenas, sem custo de spread)", "",
                  _md(metrics["pnl_by_model"]), ""]
    top = metrics["by_symbol_model"]
    if not top.empty:
        top = top[top["n"] >= 20].head(15)
        lines += ["## Top combos (symbol+model, n >= 20)", "", _md(top), ""]

    if hypothesis_results:
        lines += ["## Hipoteses avaliadas hoje", ""]
        df = pd.DataFrame([{
            "hypothesis": r["hypothesis"],
            "n": r["n"],
            "hit_t1": r.get("hit_t1", "-"),
            "ci95": f"[{r.get('ci95_low','-')}, {r.get('ci95_high','-')}]",
            "verdict": r["verdict"],
        } for r in hypothesis_results])
        lines += [_md(df), ""]
        lines.append("> Resultado registrado tambem em `vault/Hypotheses/<nome>.md` (secao 'Daily eval log').")
        lines.append("> Validacao formal via `src/research/conditional_analysis.evaluate_filter` continua manual e usa holdout protegido.")
        lines.append("")

    lines += [
        "## Caveats",
        "",
        "- Hit rate sem custo de spread/slippage. PnL aqui eh **bruto**.",
        "- Sample size de 1 dia eh ponto amostral unico. Trate combos com `n < 100` como ruido provavel.",
        "- Auto-correlacao serial nao corrigida nesta camada. CI95 de Wilson pode subestimar erro.",
        "- Para edge real, agregue 30+ dias e rode `conditional_analysis.evaluate_filter` com holdout temporal e Bonferroni.",
        "",
    ]
    return "\n".join(lines)


# =====================================================================
# Entry point
# =====================================================================

def run_for_date(date: str) -> dict:
    pred_dir = settings.data_dir / "predictions"
    research_dir = settings.data_dir / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    EVAL_DAILY_DIR.mkdir(parents=True, exist_ok=True)

    target = pd.Timestamp(date).date()
    next_day = (target + timedelta(days=1)).isoformat()

    matched_all = []
    for sym_file in sorted(pred_dir.glob("*.parquet")):
        sym = sym_file.stem
        pred = pd.read_parquet(sym_file)
        pred["timestamp"] = pd.to_datetime(pred["timestamp"], errors="coerce")
        pred = pred[pred["timestamp"].dt.date == target].copy()
        if "model_version" in pred.columns:
            pred = pred[pred["model_version"].notna()]
        if pred.empty:
            continue

        candles = load_candles_for_dates(sym, [date, next_day])
        if candles.empty:
            logger.warning(f"{sym}: sem candles para {date}")
            continue

        # Archive (idempotente, UNION+dedup)
        day_candles = candles[candles["time"].dt.date == target]
        if not day_candles.empty:
            archive_candles_for_date(date, day_candles, sym)

        matched_all.append(match_predictions_to_actuals(pred, candles))

    if not matched_all:
        logger.warning(f"{date}: sem predicoes (schema enriquecido) ou sem candles")
        return {"date": date, "status": "no_data"}

    big = pd.concat(matched_all, ignore_index=True)
    big = big.dropna(subset=["actual_t1", "actual_t2", "actual_t3"])

    eval_path = research_dir / f"eval_{date}.parquet"
    big.to_parquet(eval_path, index=False)

    metrics = aggregate_metrics(big)
    baseline = load_baseline_evals(date, days=30)
    drift = detect_drift(metrics, baseline)
    hyp_results = run_hypotheses_for_eval(big, date)

    report = render_report(date, metrics, drift, len(baseline), hyp_results)
    report_path = EVAL_DAILY_DIR / f"{date}.md"
    report_path.write_text(report, encoding="utf-8")

    return {
        "date": date,
        "status": "ok",
        "n_total": metrics["n_total"],
        "n_with_movement": metrics["n_with_movement"],
        "drift_flags": len(drift),
        "hypotheses_evaluated": len(hyp_results),
        "dataset": str(eval_path),
        "report": str(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Avaliador batch diario.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: ontem UTC)")
    parser.add_argument("--from", dest="date_from", help="Range start YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="Range end YYYY-MM-DD")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.date_from and args.date_to:
        start = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        end = datetime.strptime(args.date_to, "%Y-%m-%d").date()
        dates = [(start + timedelta(days=i)).isoformat()
                 for i in range((end - start).days + 1)]
    elif args.date:
        dates = [args.date]
    else:
        dates = [(datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()]

    for date in dates:
        logger.info(f"=== Eval {date} ===")
        res = run_for_date(date)
        logger.info(f"Resultado: {res}")


if __name__ == "__main__":
    main()
