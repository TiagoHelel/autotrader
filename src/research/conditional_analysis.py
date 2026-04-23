"""
Conditional Analysis — descoberta honesta de edges condicionais.

Reusa predicoes ja geradas (data/predictions/{symbol}.parquet) e candles raw
(data/raw/{symbol}.parquet) para construir um research dataset com outcomes
realizados + contexto (hora, sessao, regime, confidence). Em cima desse dataset
voce testa filtros (hipoteses como "XAU entre 14-15 UTC com confidence > 0.85")
e recebe metricas com intervalo de confianca + p-value.

Protecoes anti-snooping:
- Holdout temporal (ultimos X% do tempo, nunca tocado na exploracao)
- Log persistente de todos os filtros testados (filter_log.parquet)
- Warning de Bonferroni com base em quantos filtros ja foram testados
- Bloqueio de reuso do holdout para o mesmo filter_hash

Uso tipico (script):
    from src.research.conditional_analysis import (
        build_prediction_dataset, split_holdout, evaluate_filter,
    )

    df = build_prediction_dataset(
        symbols=["XAUUSD", "EURUSD"],
        start="2025-01-01", end="2026-04-01",
        model="xgboost",
    )
    df_research, df_holdout = split_holdout(df, holdout_pct=0.20)

    evaluate_filter(
        df_research,
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15), "confidence_min": 0.85},
        hypothesis="London fix + NY open criam fluxo direcional em XAU",
    )

Uso tipico (CLI):
    python -m src.research.conditional_analysis build --symbols XAUUSD,EURUSD \\
        --start 2025-01-01 --end 2026-04-01 --model xgboost

    python -m src.research.conditional_analysis test \\
        --dataset data/research/predictions_xgboost_20260414.parquet \\
        --filter '{"symbol":"XAUUSD","hour_utc":[14,15],"confidence_min":0.85}' \\
        --hypothesis "NY open flow em XAU"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config.settings import settings
from src.backtest.engine import DEFAULT_SPREADS
from src.features.regime import compute_market_regime
from src.features.session import SESSIONS, SESSION_WEIGHTS, add_session_features
from src.mt5.symbols import get_pip_value

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESEARCH_DIR = settings.data_dir / "research"
FILTER_LOG_PATH = RESEARCH_DIR / "filter_log.parquet"
HOLDOUT_USAGE_PATH = RESEARCH_DIR / "holdout_usage.parquet"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class FilterResult:
    """Retorno de evaluate_filter."""
    n_trades: int
    win_rate: float
    win_rate_ci95_low: float
    win_rate_ci95_high: float
    mean_pnl_pips: float
    mean_pnl_net_pips: float
    sharpe: float
    max_drawdown_pips: float
    p_value_vs_coinflip: float
    passes_n_min: bool
    passes_win_rate: bool
    verdict: str  # REJECTED_N | UNDERPOWERED | PROMISING | STRONG
    filter_hash: str
    hypothesis: str
    bonferroni_adjusted_p: float | None = None
    n_prior_tests: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Build dataset
# ---------------------------------------------------------------------------
def build_prediction_dataset(
    symbols: list[str],
    start: str | None = None,
    end: str | None = None,
    model: str = "xgboost",
    save: bool = True,
) -> pd.DataFrame:
    """
    Constroi research dataset juntando predicoes salvas + candles + contexto.

    Cada linha = 1 predicao historica enriquecida com outcome realizado.

    Args:
        symbols: lista de pares (ex: ["XAUUSD", "EURUSD"])
        start: data minima (inclusive, ISO), ou None
        end: data maxima (inclusive, ISO), ou None
        model: qual modelo usar do parquet de predicoes
        save: se True, persiste em data/research/

    Returns:
        DataFrame com colunas documentadas em _enrich_predictions.
    """
    rows = []
    for symbol in symbols:
        df = _load_symbol_predictions(symbol, model=model, start=start, end=end)
        if df.empty:
            logger.warning(f"[research] {symbol}: sem predicoes — skip")
            continue
        price_df = _load_symbol_candles(symbol)
        if price_df.empty:
            logger.warning(f"[research] {symbol}: sem candles raw — skip")
            continue
        enriched = _enrich_predictions(df, price_df, symbol)
        rows.append(enriched)

    if not rows:
        logger.warning("[research] nenhum simbolo produziu dados")
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)
    result = result.sort_values("timestamp").reset_index(drop=True)

    if save:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = RESEARCH_DIR / f"predictions_{model}_{stamp}.parquet"
        result.to_parquet(path, index=False)
        logger.info(f"[research] dataset salvo: {path} ({len(result)} linhas)")

    return result


def _load_symbol_predictions(
    symbol: str, model: str, start: str | None, end: str | None,
) -> pd.DataFrame:
    path = settings.predictions_dir / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if "model" in df.columns:
        df = df[df["model"] == model]
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    if start:
        df = df[df["timestamp"] >= pd.to_datetime(start)]
    if end:
        df = df[df["timestamp"] <= pd.to_datetime(end)]
    return df.reset_index(drop=True)


def _load_symbol_candles(symbol: str) -> pd.DataFrame:
    path = settings.raw_dir / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def _enrich_predictions(
    pred_df: pd.DataFrame, price_df: pd.DataFrame, symbol: str,
) -> pd.DataFrame:
    """
    Junta predicoes com outcomes realizados e contexto.

    Colunas resultantes:
        symbol, timestamp, model,
        hour_utc, hour_local_ny, session, session_score,
        trend, volatility_regime, momentum,
        current_price, pred_t1, pred_t2, pred_t3,
        predicted_direction, confidence, expected_return,
        actual_price_t1, actual_price_t3,
        actual_direction_t1, actual_return_t1_pips,
        pnl_if_traded_pips, pnl_if_traded_net_pips,
        signal  (BUY/SELL/HOLD reconstruido).
    """
    pip_value = get_pip_value(symbol)
    spread_pips = DEFAULT_SPREADS.get(symbol, 2.0)

    # ---- contexto: regime requer features tecnicas. Recomputamos minimal ----
    ctx = _compute_context_frame(price_df, symbol)
    # ---- mapear cada predicao ao candle imediatamente seguinte ----
    price_df = price_df.sort_values("time").reset_index(drop=True)
    times = price_df["time"].values

    rows = []
    for _, p in pred_df.iterrows():
        t_pred = pd.Timestamp(p["timestamp"])
        # primeiro candle com time > t_pred
        idx = np.searchsorted(times, np.datetime64(t_pred), side="right")
        if idx >= len(price_df) - 3:
            continue  # sem candles futuros suficientes pra t+3

        current_price = float(p.get("current_price", price_df.iloc[idx - 1]["close"] if idx > 0 else np.nan))
        pred_t1 = float(p.get("pred_t1", current_price))
        pred_t2 = float(p.get("pred_t2", current_price))
        pred_t3 = float(p.get("pred_t3", current_price))

        actual_t1 = float(price_df.iloc[idx]["close"])
        actual_t3 = float(price_df.iloc[idx + 2]["close"])

        # retorno esperado ponderado (mesma formula do signal.py)
        if current_price > 0:
            ret = (
                (pred_t1 - current_price) * 0.5
                + (pred_t2 - current_price) * 0.3
                + (pred_t3 - current_price) * 0.2
            ) / current_price
        else:
            ret = 0.0

        predicted_dir = 1 if ret > 0 else (-1 if ret < 0 else 0)
        signal = "BUY" if ret > 0.0003 else ("SELL" if ret < -0.0003 else "HOLD")

        # confidence: concordancia entre horizontes + magnitude vs threshold
        dirs = [
            np.sign(pred_t1 - current_price),
            np.sign(pred_t2 - current_price),
            np.sign(pred_t3 - current_price),
        ]
        agreement = abs(sum(dirs)) / 3.0
        magnitude = min(abs(ret) / 0.0003, 1.0) if ret else 0.0
        confidence = float(agreement * 0.6 + magnitude * 0.4)

        # outcome realizado
        actual_return_t1 = actual_t1 - current_price
        actual_dir_t1 = 1 if actual_return_t1 > 0 else (-1 if actual_return_t1 < 0 else 0)
        actual_return_t1_pips = actual_return_t1 / pip_value

        # PnL se tivesse operado (exit em t+3, como o backtest default)
        pnl_pips = 0.0
        pnl_net_pips = 0.0
        if signal == "BUY":
            pnl_pips = (actual_t3 - current_price) / pip_value
            pnl_net_pips = pnl_pips - spread_pips
        elif signal == "SELL":
            pnl_pips = (current_price - actual_t3) / pip_value
            pnl_net_pips = pnl_pips - spread_pips
        # HOLD → 0

        # Contexto no instante da predicao
        ctx_row = _lookup_context(ctx, t_pred)

        rows.append({
            "symbol": symbol,
            "timestamp": t_pred,
            "model": p.get("model", "unknown"),
            "hour_utc": int(t_pred.hour),
            "hour_local_ny": int((t_pred.hour - 4) % 24),  # aprox NY EST (nao DST-aware)
            "session": ctx_row["session"],
            "session_score": float(ctx_row["session_score"]),
            "trend": int(ctx_row["trend"]),
            "volatility_regime": int(ctx_row["volatility_regime"]),
            "momentum": float(ctx_row["momentum"]),
            "current_price": current_price,
            "pred_t1": pred_t1,
            "pred_t2": pred_t2,
            "pred_t3": pred_t3,
            "predicted_direction": predicted_dir,
            "confidence": confidence,
            "expected_return": float(ret),
            "signal": signal,
            "actual_price_t1": actual_t1,
            "actual_price_t3": actual_t3,
            "actual_direction_t1": actual_dir_t1,
            "actual_return_t1_pips": float(actual_return_t1_pips),
            "pnl_if_traded_pips": float(pnl_pips),
            "pnl_if_traded_net_pips": float(pnl_net_pips),
        })

    return pd.DataFrame(rows)


def _compute_context_frame(price_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Gera frame indexado por 'time' com session + regime features minimos.
    So precisa das features que alimentam contexto condicional, nao o modelo.
    """
    df = price_df.copy()
    # EMAs/ATR/vol_20 minimos pro regime
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    tr = pd.concat([
        (df["high"] - df["low"]),
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["vol_20"] = df["close"].pct_change().rolling(20).std()

    df = compute_market_regime(df)
    df = add_session_features(df, symbol=symbol)

    # primary session label
    df["session"] = df.apply(_primary_session_label, axis=1)

    keep = ["time", "session", "session_score", "trend", "volatility_regime", "momentum"]
    return df[keep].copy()


def _primary_session_label(row: pd.Series) -> str:
    """Retorna label da sessao dominante para a linha (prioriza overlaps)."""
    if row.get("session_overlap_london_ny", 0):
        return "london_ny_overlap"
    if row.get("session_overlap_tokyo_london", 0):
        return "tokyo_london_overlap"
    for name in ("new_york", "london", "tokyo", "sydney"):
        if row.get(f"session_{name}", 0):
            return name
    return "off_hours"


def _lookup_context(ctx: pd.DataFrame, t: pd.Timestamp) -> dict:
    """Busca linha de contexto mais proxima <= t (backward fill)."""
    idx = np.searchsorted(ctx["time"].values, np.datetime64(t), side="right") - 1
    if idx < 0:
        return {
            "session": "off_hours", "session_score": 0.0,
            "trend": 0, "volatility_regime": 1, "momentum": 0.0,
        }
    return ctx.iloc[idx].to_dict()


# ---------------------------------------------------------------------------
# Holdout split
# ---------------------------------------------------------------------------
def split_holdout(
    df: pd.DataFrame, holdout_pct: float = 0.20, method: str = "temporal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Divide dataset em research (exploracao) e holdout (validacao final).

    - method="temporal": holdout e o final do periodo (recomendado p/ series temporais)
    - method="random": sample aleatorio (nao recomendado, presente para sanity tests)
    """
    if df.empty:
        return df, df
    if method == "temporal":
        df = df.sort_values("timestamp").reset_index(drop=True)
        cut = int(len(df) * (1 - holdout_pct))
        return df.iloc[:cut].copy(), df.iloc[cut:].copy()
    if method == "random":
        shuffled = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        cut = int(len(shuffled) * (1 - holdout_pct))
        return shuffled.iloc[:cut].copy(), shuffled.iloc[cut:].copy()
    raise ValueError(f"method invalido: {method}")


# ---------------------------------------------------------------------------
# Evaluate filter
# ---------------------------------------------------------------------------
N_MIN_SIGNIFICANT = 30
WIN_RATE_MIN = 0.50


def evaluate_filter(
    df: pd.DataFrame,
    filters: dict,
    hypothesis: str,
    holdout: bool = False,
    log: bool = True,
) -> FilterResult:
    """
    Aplica filtros ao dataset e calcula metricas + p-value + verdict.

    Args:
        df: dataset de pesquisa (vindo de build_prediction_dataset / split_holdout)
        filters: dict. Chaves suportadas:
            - "symbol": str (exact match)
            - "model": str (exact match)
            - "hour_utc": (min, max)  # [min, max), 24h
            - "session": str ou list[str]
            - "signal": str ou list[str]  # BUY/SELL/HOLD
            - "trend": int (1/-1/0)
            - "volatility_regime": int (0/1/2)
            - "confidence": (min, max)
            - "confidence_min": float (atalho p/ (min, 1.0))
            - "session_score": (min, max)
        hypothesis: texto curto descrevendo por que esse filtro deveria funcionar
        holdout: True se df e dataset holdout. Protege contra reuso.
        log: se True, persiste teste em filter_log.parquet

    Returns:
        FilterResult. Tambem printa sumario legivel.
    """
    filtered = _apply_filters(df, filters)
    signal_col = "signal"
    # HOLDs nao sao trades — considere apenas BUY/SELL pro calculo de performance
    traded = filtered[filtered[signal_col].isin(["BUY", "SELL"])].copy()

    n = len(traded)
    filter_hash = _hash_filters(filters)

    if n == 0:
        result = FilterResult(
            n_trades=0, win_rate=0.0,
            win_rate_ci95_low=0.0, win_rate_ci95_high=0.0,
            mean_pnl_pips=0.0, mean_pnl_net_pips=0.0,
            sharpe=0.0, max_drawdown_pips=0.0,
            p_value_vs_coinflip=1.0,
            passes_n_min=False, passes_win_rate=False,
            verdict="REJECTED_N",
            filter_hash=filter_hash, hypothesis=hypothesis,
        )
    else:
        wins = (traded["pnl_if_traded_net_pips"] > 0).sum()
        win_rate = wins / n
        ci_low, ci_high = _wilson_ci(wins, n, alpha=0.05)
        mean_pnl = float(traded["pnl_if_traded_pips"].mean())
        mean_pnl_net = float(traded["pnl_if_traded_net_pips"].mean())
        std_net = float(traded["pnl_if_traded_net_pips"].std(ddof=1)) if n > 1 else 0.0
        sharpe = (mean_pnl_net / std_net * math.sqrt(252 * 78)) if std_net > 0 else 0.0  # M5 ~78/dia
        equity = traded["pnl_if_traded_net_pips"].cumsum().values
        max_dd = float((equity - np.maximum.accumulate(equity)).min()) if len(equity) else 0.0
        p_value = _binomial_test_two_sided(wins, n, p=0.5)

        passes_n = n >= N_MIN_SIGNIFICANT
        passes_wr = ci_low > WIN_RATE_MIN

        if not passes_n:
            verdict = "UNDERPOWERED"
        elif passes_wr and p_value < 0.05:
            verdict = "STRONG" if p_value < 0.01 else "PROMISING"
        elif win_rate > WIN_RATE_MIN:
            verdict = "WEAK"
        else:
            verdict = "REJECTED_WR"

        result = FilterResult(
            n_trades=n,
            win_rate=round(win_rate, 4),
            win_rate_ci95_low=round(ci_low, 4),
            win_rate_ci95_high=round(ci_high, 4),
            mean_pnl_pips=round(mean_pnl, 3),
            mean_pnl_net_pips=round(mean_pnl_net, 3),
            sharpe=round(sharpe, 3),
            max_drawdown_pips=round(max_dd, 2),
            p_value_vs_coinflip=round(p_value, 6),
            passes_n_min=passes_n,
            passes_win_rate=passes_wr,
            verdict=verdict,
            filter_hash=filter_hash,
            hypothesis=hypothesis,
        )

    # Bonferroni + persistencia
    if log:
        n_prior = _count_prior_tests()
        result.n_prior_tests = n_prior
        if n_prior > 0 and result.p_value_vs_coinflip < 1.0:
            result.bonferroni_adjusted_p = min(
                1.0, result.p_value_vs_coinflip * (n_prior + 1)
            )
        _persist_filter_log(result, filters, holdout=holdout)

    if holdout:
        _check_holdout_reuse(result.filter_hash)
        _record_holdout_usage(result.filter_hash)

    _print_filter_summary(result, filters)
    return result


def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df
    for key, val in filters.items():
        if out.empty:
            return out
        if key == "symbol":
            out = out[out["symbol"] == val]
        elif key == "model":
            out = out[out["model"] == val]
        elif key == "hour_utc":
            lo, hi = val
            out = out[(out["hour_utc"] >= lo) & (out["hour_utc"] < hi)]
        elif key == "session":
            if isinstance(val, (list, tuple, set)):
                out = out[out["session"].isin(list(val))]
            else:
                out = out[out["session"] == val]
        elif key == "signal":
            if isinstance(val, (list, tuple, set)):
                out = out[out["signal"].isin(list(val))]
            else:
                out = out[out["signal"] == val]
        elif key == "trend":
            out = out[out["trend"] == val]
        elif key == "volatility_regime":
            out = out[out["volatility_regime"] == val]
        elif key == "confidence":
            lo, hi = val
            out = out[(out["confidence"] >= lo) & (out["confidence"] <= hi)]
        elif key == "confidence_min":
            out = out[out["confidence"] >= val]
        elif key == "session_score":
            lo, hi = val
            out = out[(out["session_score"] >= lo) & (out["session_score"] <= hi)]
        else:
            logger.warning(f"[research] filtro ignorado (desconhecido): {key}")
    return out


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def _wilson_ci(wins: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Intervalo de confianca Wilson — robusto para n pequeno."""
    if n == 0:
        return 0.0, 0.0
    from math import sqrt
    z = 1.959963984540054  # 95% two-sided
    p = wins / n
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (center - margin) / denom, (center + margin) / denom


def _binomial_test_two_sided(wins: int, n: int, p: float = 0.5) -> float:
    """P-value two-sided pro teste binomial (wins/n vs p=0.5)."""
    if n == 0:
        return 1.0
    try:
        from scipy.stats import binomtest
        return float(binomtest(wins, n, p=p, alternative="two-sided").pvalue)
    except Exception:
        # fallback sem scipy: aproximacao normal
        from math import sqrt, erf
        mean = n * p
        sd = sqrt(n * p * (1 - p))
        if sd == 0:
            return 1.0
        z = abs(wins - mean) / sd
        # two-sided p
        return float(2 * (1 - 0.5 * (1 + erf(z / sqrt(2)))))


def _hash_filters(filters: dict) -> str:
    """Hash estavel do dict de filtros (ordem-independente)."""
    payload = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Persistence (filter log + holdout usage)
# ---------------------------------------------------------------------------
def _persist_filter_log(result: FilterResult, filters: dict, holdout: bool) -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now().isoformat(),
        "filter_hash": result.filter_hash,
        "filters_json": json.dumps(filters, default=str, sort_keys=True),
        "hypothesis": result.hypothesis,
        "holdout": holdout,
        **{k: v for k, v in result.to_dict().items()
           if k not in ("filter_hash", "hypothesis")},
    }
    new_df = pd.DataFrame([row])
    if FILTER_LOG_PATH.exists():
        old = pd.read_parquet(FILTER_LOG_PATH)
        combined = pd.concat([old, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_parquet(FILTER_LOG_PATH, index=False)


def _count_prior_tests() -> int:
    if not FILTER_LOG_PATH.exists():
        return 0
    df = pd.read_parquet(FILTER_LOG_PATH)
    # considera apenas testes em research (nao holdout) para Bonferroni
    return int((df.get("holdout", False) == False).sum())  # noqa: E712


def _check_holdout_reuse(filter_hash: str) -> None:
    if not HOLDOUT_USAGE_PATH.exists():
        return
    used = pd.read_parquet(HOLDOUT_USAGE_PATH)
    if (used["filter_hash"] == filter_hash).any():
        logger.warning(
            f"[research] ATENCAO: filter_hash {filter_hash} ja foi validado em holdout. "
            f"Reuso quebra garantia estatistica — resultado deste teste e INVALIDO."
        )


def _record_holdout_usage(filter_hash: str) -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{
        "filter_hash": filter_hash,
        "timestamp": datetime.now().isoformat(),
    }])
    if HOLDOUT_USAGE_PATH.exists():
        old = pd.read_parquet(HOLDOUT_USAGE_PATH)
        pd.concat([old, row], ignore_index=True).to_parquet(HOLDOUT_USAGE_PATH, index=False)
    else:
        row.to_parquet(HOLDOUT_USAGE_PATH, index=False)


# ---------------------------------------------------------------------------
# Pretty print
# ---------------------------------------------------------------------------
def _print_filter_summary(r: FilterResult, filters: dict) -> None:
    filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
    print(f"\n[FILTER] {filter_str}")
    print(f"  Hypothesis: {r.hypothesis}")
    print(
        f"  N={r.n_trades} | WR={r.win_rate*100:.1f}% "
        f"[{r.win_rate_ci95_low*100:.1f}-{r.win_rate_ci95_high*100:.1f}%] | "
        f"PnL_net={r.mean_pnl_net_pips:.2f} pips/trade | "
        f"Sharpe={r.sharpe:.2f} | MaxDD={r.max_drawdown_pips:.1f} pips"
    )
    print(f"  p-value vs coinflip: {r.p_value_vs_coinflip:.4f}")
    if r.bonferroni_adjusted_p is not None:
        print(
            f"  Bonferroni ajustado ({r.n_prior_tests} testes previos): "
            f"p = {r.bonferroni_adjusted_p:.4f}"
            + (" → NAO significativo" if r.bonferroni_adjusted_p >= 0.05 else "")
        )
    print(f"  Verdict: {r.verdict}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli():
    parser = argparse.ArgumentParser(prog="conditional_analysis")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Gera research dataset")
    p_build.add_argument("--symbols", required=True, help="CSV: XAUUSD,EURUSD")
    p_build.add_argument("--start", default=None)
    p_build.add_argument("--end", default=None)
    p_build.add_argument("--model", default="xgboost")

    p_test = sub.add_parser("test", help="Testa filtro num dataset existente")
    p_test.add_argument("--dataset", required=True, help="Path do parquet")
    p_test.add_argument("--filter", required=True, help="JSON do dict de filtros")
    p_test.add_argument("--hypothesis", required=True)
    p_test.add_argument("--holdout", action="store_true")
    p_test.add_argument("--holdout-pct", type=float, default=0.20)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if args.cmd == "build":
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        build_prediction_dataset(symbols, start=args.start, end=args.end, model=args.model)
    elif args.cmd == "test":
        df = pd.read_parquet(args.dataset)
        filters = json.loads(args.filter)
        # converter listas JSON em tuplas onde aplicavel
        for k in ("hour_utc", "confidence", "session_score"):
            if k in filters and isinstance(filters[k], list):
                filters[k] = tuple(filters[k])
        if args.holdout:
            _, df_h = split_holdout(df, holdout_pct=args.holdout_pct)
            evaluate_filter(df_h, filters, hypothesis=args.hypothesis, holdout=True)
        else:
            df_r, _ = split_holdout(df, holdout_pct=args.holdout_pct)
            evaluate_filter(df_r, filters, hypothesis=args.hypothesis, holdout=False)


if __name__ == "__main__":
    _cli()
