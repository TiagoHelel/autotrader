"""
Session de mercado Forex como features para modelos ML.

Detecta sessoes ativas (Sydney, Tokyo, London, New York),
overlaps, session strength e score ponderado por ativo.

Horarios em UTC:
  Sydney:   22:00 - 07:00
  Tokyo:    00:00 - 09:00
  London:   08:00 - 17:00
  New York: 13:00 - 22:00
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definicao das sessoes (UTC)
# ---------------------------------------------------------------------------
SESSIONS = {
    "sydney":   {"start": 22, "end": 7},   # 22:00 - 07:00 UTC
    "tokyo":    {"start": 0,  "end": 9},    # 00:00 - 09:00 UTC
    "london":   {"start": 8,  "end": 17},   # 08:00 - 17:00 UTC
    "new_york": {"start": 13, "end": 22},   # 13:00 - 22:00 UTC
}

# Overlaps conhecidos
OVERLAPS = {
    "overlap_tokyo_london":  {"start": 8,  "end": 9},   # Tokyo + London
    "overlap_london_ny":     {"start": 13, "end": 17},   # London + NY
}

# ---------------------------------------------------------------------------
# Pesos por ativo — quão relevante cada sessao e para cada par
# Escala 0.0 - 1.0
# ---------------------------------------------------------------------------
SESSION_WEIGHTS = {
    "EURUSD": {
        "sydney": 0.1, "tokyo": 0.2, "london": 0.9, "new_york": 0.8,
    },
    "GBPUSD": {
        "sydney": 0.1, "tokyo": 0.15, "london": 0.95, "new_york": 0.7,
    },
    "USDJPY": {
        "sydney": 0.3, "tokyo": 0.95, "london": 0.5, "new_york": 0.6,
    },
    "USDCHF": {
        "sydney": 0.1, "tokyo": 0.2, "london": 0.85, "new_york": 0.7,
    },
    "AUDUSD": {
        "sydney": 0.9, "tokyo": 0.7, "london": 0.4, "new_york": 0.5,
    },
    "USDCAD": {
        "sydney": 0.1, "tokyo": 0.15, "london": 0.5, "new_york": 0.9,
    },
    "NZDUSD": {
        "sydney": 0.85, "tokyo": 0.65, "london": 0.35, "new_york": 0.45,
    },
    "EURGBP": {
        "sydney": 0.05, "tokyo": 0.15, "london": 0.95, "new_york": 0.4,
    },
    "EURJPY": {
        "sydney": 0.2, "tokyo": 0.8, "london": 0.85, "new_york": 0.5,
    },
    "GBPJPY": {
        "sydney": 0.2, "tokyo": 0.85, "london": 0.9, "new_york": 0.5,
    },
    "XAUUSD": {
        "sydney": 0.15, "tokyo": 0.3, "london": 0.85, "new_york": 0.9,
    },
}

# Default para pares nao mapeados
_DEFAULT_WEIGHTS = {"sydney": 0.2, "tokyo": 0.3, "london": 0.7, "new_york": 0.7}

# Colunas geradas por este modulo
SESSION_FEATURE_COLUMNS = [
    "session_sydney",
    "session_tokyo",
    "session_london",
    "session_new_york",
    "session_overlap_london_ny",
    "session_overlap_tokyo_london",
    "session_strength",
    "session_score",
]


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------
def _is_session_active(hour: int, start: int, end: int) -> bool:
    """Verifica se a hora UTC esta dentro de uma sessao (suporta cross-midnight)."""
    if start < end:
        return start <= hour < end
    # Cross midnight (ex: Sydney 22-07)
    return hour >= start or hour < end


def _get_active_sessions(hour: int) -> dict[str, int]:
    """Retorna dict com 0/1 para cada sessao."""
    return {
        name: int(_is_session_active(hour, s["start"], s["end"]))
        for name, s in SESSIONS.items()
    }


def _get_overlaps(hour: int) -> dict[str, int]:
    """Retorna dict com 0/1 para cada overlap."""
    return {
        name: int(_is_session_active(hour, o["start"], o["end"]))
        for name, o in OVERLAPS.items()
    }


def _compute_strength(active_sessions: dict[str, int]) -> int:
    """Session strength: 0 (fechado) a 3 (3+ sessoes ativas)."""
    count = sum(active_sessions.values())
    return min(count, 3)


def _compute_score(active_sessions: dict[str, int], symbol: str) -> float:
    """Score ponderado: soma dos pesos das sessoes ativas para o ativo."""
    weights = SESSION_WEIGHTS.get(symbol, _DEFAULT_WEIGHTS)
    score = sum(
        active * weights.get(session, 0.0)
        for session, active in active_sessions.items()
    )
    # Normalizar para 0-1 (max possivel = soma de todos os pesos)
    max_score = sum(weights.values())
    return round(score / max_score, 4) if max_score > 0 else 0.0


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def compute_session_features(timestamp, symbol: str = None) -> dict:
    """
    Computa todas as features de sessao para um timestamp.

    Args:
        timestamp: datetime ou pd.Timestamp (UTC)
        symbol: par forex (para session_score). Se None, usa pesos default.

    Returns:
        dict com session_sydney, session_tokyo, session_london, session_new_york,
        session_overlap_london_ny, session_overlap_tokyo_london,
        session_strength, session_score
    """
    if pd.isna(timestamp):
        return {col: 0.0 for col in SESSION_FEATURE_COLUMNS}

    ts = pd.Timestamp(timestamp)
    hour = ts.hour

    active = _get_active_sessions(hour)
    overlaps = _get_overlaps(hour)
    strength = _compute_strength(active)
    score = _compute_score(active, symbol) if symbol else 0.0

    return {
        "session_sydney": active["sydney"],
        "session_tokyo": active["tokyo"],
        "session_london": active["london"],
        "session_new_york": active["new_york"],
        "session_overlap_london_ny": overlaps["overlap_london_ny"],
        "session_overlap_tokyo_london": overlaps["overlap_tokyo_london"],
        "session_strength": strength,
        "session_score": score,
    }


def add_session_features(df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
    """
    Adiciona colunas de sessao a um DataFrame com coluna 'time'.

    Vetorizado para performance com DataFrames grandes.

    Args:
        df: DataFrame com coluna 'time' (datetime UTC)
        symbol: par forex para calculo de session_score

    Returns:
        DataFrame com colunas de sessao adicionadas
    """
    if df.empty or "time" not in df.columns:
        for col in SESSION_FEATURE_COLUMNS:
            df[col] = 0.0
        return df

    times = pd.to_datetime(df["time"])
    hours = times.dt.hour

    # Sessoes (vetorizado)
    for name, session in SESSIONS.items():
        start, end = session["start"], session["end"]
        if start < end:
            df[f"session_{name}"] = ((hours >= start) & (hours < end)).astype(int)
        else:
            df[f"session_{name}"] = ((hours >= start) | (hours < end)).astype(int)

    # Overlaps (vetorizado)
    for name, overlap in OVERLAPS.items():
        start, end = overlap["start"], overlap["end"]
        df[f"session_{name}"] = ((hours >= start) & (hours < end)).astype(int)

    # Strength
    session_cols = ["session_sydney", "session_tokyo", "session_london", "session_new_york"]
    df["session_strength"] = df[session_cols].sum(axis=1).clip(upper=3).astype(int)

    # Score
    weights = SESSION_WEIGHTS.get(symbol, _DEFAULT_WEIGHTS) if symbol else _DEFAULT_WEIGHTS
    max_score = sum(weights.values())
    if max_score > 0:
        df["session_score"] = (
            df["session_sydney"] * weights.get("sydney", 0)
            + df["session_tokyo"] * weights.get("tokyo", 0)
            + df["session_london"] * weights.get("london", 0)
            + df["session_new_york"] * weights.get("new_york", 0)
        ) / max_score
        df["session_score"] = df["session_score"].round(4)
    else:
        df["session_score"] = 0.0

    logger.debug(f"Session features adicionadas: {len(df)} rows, symbol={symbol}")
    return df


def get_current_session_info(symbol: str = None) -> dict:
    """
    Retorna informacoes da sessao atual (now UTC).

    Usado pela API para expor estado atual das sessoes.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    features = compute_session_features(now, symbol)

    active_sessions = []
    for name in SESSIONS:
        if features.get(f"session_{name}", 0):
            active_sessions.append(name)

    active_overlaps = []
    for name in OVERLAPS:
        if features.get(f"session_{name}", 0):
            active_overlaps.append(name)

    weights = SESSION_WEIGHTS.get(symbol, _DEFAULT_WEIGHTS) if symbol else _DEFAULT_WEIGHTS

    return {
        "timestamp_utc": now.isoformat(),
        "hour_utc": now.hour,
        "active_sessions": active_sessions,
        "active_overlaps": active_overlaps,
        "session_strength": features["session_strength"],
        "session_score": features["session_score"],
        "symbol": symbol,
        "weights": weights,
        "features": features,
    }
