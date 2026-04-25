"""
Auto-selecao de modelo baseada em regime de mercado.
Seleciona o melhor modelo para cada par/regime com base em historico de performance.
"""

import logging

import pandas as pd

from config.settings import settings
from src.research.model_ranking import get_best_model

logger = logging.getLogger(__name__)


def select_model(symbol: str, regime: dict = None, session: str = None) -> dict:
    """
    Seleciona o melhor modelo para um simbolo com base no regime e sessao atuais.

    Args:
        symbol: par de moedas
        regime: dict com {trend, volatility_regime, range_flag}
                Se None, retorna o melhor modelo global.
        session: nome da sessao ativa principal (ex: "london", "new_york")
                 Se fornecido, tenta selecionar modelo com melhor performance
                 historica nessa sessao.

    Returns:
        {
            "model": str,
            "score": float,
            "reason": str,
            "regime_match": bool,
            "session_match": bool,
        }
    """
    # 1. Tentar selecionar por sessao + regime (mais especifico)
    if session and regime:
        session_regime_model = _select_by_session(symbol, session, regime)
        if session_regime_model:
            return session_regime_model

    # 2. Tentar selecionar por sessao apenas
    if session:
        session_model = _select_by_session(symbol, session)
        if session_model:
            return session_model

    # 3. Tentar selecionar por regime
    if regime:
        regime_model = _select_by_regime(symbol, regime)
        if regime_model:
            regime_model["session_match"] = False
            return regime_model

    # 4. Fallback: melhor modelo global
    best = get_best_model(symbol)
    if best:
        return {
            "model": best.get("model", "unknown"),
            "score": float(best.get("score", 0)),
            "reason": "best overall score",
            "regime_match": False,
            "session_match": False,
        }

    return {"model": "xgboost", "score": 0, "reason": "default fallback", "regime_match": False, "session_match": False}


def select_models_by_regime(symbol: str) -> dict:
    """
    Retorna o melhor modelo para cada regime de um simbolo.

    Returns:
        {
            "trend_bull": {"model": ..., "score": ...},
            "trend_bear": {"model": ..., "score": ...},
            "high_vol": {"model": ..., "score": ...},
            "low_vol": {"model": ..., "score": ...},
            "ranging": {"model": ..., "score": ...},
            "trending": {"model": ..., "score": ...},
        }
    """
    regimes = {
        "trend_bull": {"trend": 1},
        "trend_bear": {"trend": -1},
        "high_vol": {"volatility_regime": 2},
        "low_vol": {"volatility_regime": 0},
        "ranging": {"range_flag": 1},
        "trending": {"range_flag": 0},
    }

    results = {}
    for regime_name, regime_filter in regimes.items():
        best = _select_by_regime(symbol, regime_filter)
        results[regime_name] = best or {"model": "unknown", "score": 0, "reason": "no data"}

    return results


def _select_by_regime(symbol: str, regime: dict) -> dict | None:
    """Seleciona modelo com base em performance historica por regime."""
    # Carregar backtest trades com info de regime
    bt_dir = settings.data_dir / "backtest"
    if not bt_dir.exists():
        return None

    all_trades = []
    for f in bt_dir.glob(f"{symbol}_*.parquet"):
        if "_metrics" in f.stem:
            continue
        try:
            df = pd.read_parquet(f)
            all_trades.append(df)
        except Exception:
            continue

    if not all_trades:
        return None

    trades_df = pd.concat(all_trades, ignore_index=True)
    if trades_df.empty:
        return None

    # Carregar features para obter regime em cada timestamp
    features_file = settings.features_dir / f"{symbol}.parquet"
    if not features_file.exists():
        return None

    features_df = pd.read_parquet(features_file)
    features_df["time"] = pd.to_datetime(features_df["time"])

    # Para cada trade, encontrar regime do momento
    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])

    # Merge approximate: encontrar regime mais proximo
    trades_with_regime = pd.merge_asof(
        trades_df.sort_values("entry_time"),
        features_df[["time", "trend", "volatility_regime", "range_flag"]].sort_values("time"),
        left_on="entry_time",
        right_on="time",
        direction="backward",
    )

    # Filtrar pelo regime solicitado
    mask = pd.Series(True, index=trades_with_regime.index)
    for key, value in regime.items():
        if key in trades_with_regime.columns:
            mask &= trades_with_regime[key] == value

    filtered = trades_with_regime[mask]
    if filtered.empty or "model" not in filtered.columns:
        return None

    # Calcular performance por modelo no regime filtrado
    perf = filtered.groupby("model").agg(
        pnl=("pnl_pips", "sum"),
        trades=("pnl_pips", "count"),
        winrate=("pnl_pips", lambda x: (x > 0).mean() * 100),
    ).reset_index()

    if perf.empty:
        return None

    # Melhor modelo por PnL
    best = perf.loc[perf["pnl"].idxmax()]
    regime_desc = ", ".join(f"{k}={v}" for k, v in regime.items())

    return {
        "model": best["model"],
        "score": float(best["pnl"]),
        "pnl": float(best["pnl"]),
        "trades": int(best["trades"]),
        "winrate": round(float(best["winrate"]), 1),
        "reason": f"best in regime ({regime_desc})",
        "regime_match": True,
        "session_match": False,
    }


def _select_by_session(symbol: str, session: str, regime: dict = None) -> dict | None:
    """Seleciona modelo com base em performance historica por sessao de mercado."""
    bt_dir = settings.data_dir / "backtest"
    if not bt_dir.exists():
        return None

    all_trades = []
    for f in bt_dir.glob(f"{symbol}_*.parquet"):
        if "_metrics" in f.stem:
            continue
        try:
            df = pd.read_parquet(f)
            all_trades.append(df)
        except Exception:
            continue

    if not all_trades:
        return None

    trades_df = pd.concat(all_trades, ignore_index=True)
    if trades_df.empty or "entry_time" not in trades_df.columns:
        return None

    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])

    # Carregar features para obter sessao em cada timestamp
    features_file = settings.features_dir / f"{symbol}.parquet"
    if not features_file.exists():
        return None

    features_df = pd.read_parquet(features_file)
    features_df["time"] = pd.to_datetime(features_df["time"])

    session_col = f"session_{session}"
    merge_cols = ["time"]
    feature_cols = [session_col]

    # Se temos regime, incluir colunas de regime no merge
    if regime:
        feature_cols.extend([k for k in regime.keys() if k in features_df.columns])

    available_cols = [c for c in feature_cols if c in features_df.columns]
    if session_col not in available_cols:
        return None

    trades_with_session = pd.merge_asof(
        trades_df.sort_values("entry_time"),
        features_df[merge_cols + available_cols].sort_values("time"),
        left_on="entry_time",
        right_on="time",
        direction="backward",
    )

    # Filtrar trades onde a sessao estava ativa
    mask = trades_with_session[session_col] == 1

    # Adicionalmente filtrar por regime se fornecido
    if regime:
        for key, value in regime.items():
            if key in trades_with_session.columns:
                mask &= trades_with_session[key] == value

    filtered = trades_with_session[mask]
    if filtered.empty or "model" not in filtered.columns:
        return None

    # Calcular performance por modelo na sessao filtrada
    perf = filtered.groupby("model").agg(
        pnl=("pnl_pips", "sum"),
        trades=("pnl_pips", "count"),
        winrate=("pnl_pips", lambda x: (x > 0).mean() * 100),
    ).reset_index()

    if perf.empty:
        return None

    # Minimo de trades para ser considerado (evitar overfitting)
    perf = perf[perf["trades"] >= 5]
    if perf.empty:
        return None

    best = perf.loc[perf["pnl"].idxmax()]
    regime_desc = f"session={session}"
    if regime:
        regime_desc += ", " + ", ".join(f"{k}={v}" for k, v in regime.items())

    return {
        "model": best["model"],
        "score": float(best["pnl"]),
        "pnl": float(best["pnl"]),
        "trades": int(best["trades"]),
        "winrate": round(float(best["winrate"]), 1),
        "reason": f"best in {regime_desc}",
        "regime_match": regime is not None,
        "session_match": True,
    }


def get_primary_session(symbol: str = None) -> str | None:
    """Retorna a sessao principal ativa no momento (a mais relevante para o ativo)."""
    from src.features.session import get_current_session_info

    info = get_current_session_info(symbol)
    active = info.get("active_sessions", [])
    if not active:
        return None

    if len(active) == 1:
        return active[0]

    # Se multiplas sessoes, retornar a com maior peso para o ativo
    weights = info.get("weights", {})
    return max(active, key=lambda s: weights.get(s, 0))
