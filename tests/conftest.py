"""Fixtures compartilhadas para testes."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Adiciona root do projeto ao path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """
    Gera dataset sintetico realista com candles OHLC + tick_volume + spread.
    500 barras M5 com random walk + sazonalidade intradia para exercer
    features tecnicas (RSI, EMA, ATR, vol rolling) e regime.
    """
    rng = np.random.default_rng(42)
    n = 500
    start = pd.Timestamp("2025-01-02 00:00:00")
    times = pd.date_range(start, periods=n, freq="5min")

    # Random walk para close, com drift leve
    steps = rng.normal(loc=0.0, scale=0.0005, size=n)
    # leve sazonalidade por hora
    hours = times.hour + times.minute / 60.0
    season = 0.0002 * np.sin(2 * np.pi * hours / 24.0)
    log_returns = steps + season
    close = 1.10 * np.exp(np.cumsum(log_returns))  # começa em ~1.10 (EURUSD)

    # OHLC derivado
    noise = rng.normal(0, 0.0003, size=n)
    open_ = np.concatenate([[close[0]], close[:-1]]) + noise * 0.2
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0004, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0004, size=n))
    tick_volume = rng.integers(50, 500, size=n).astype(float)
    spread = rng.integers(1, 5, size=n).astype(float)

    df = pd.DataFrame({
        "time": times,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": tick_volume,
        "spread": spread,
    })
    return df


@pytest.fixture
def sample_features(sample_data: pd.DataFrame) -> pd.DataFrame:
    """Dataset com features computadas via pipeline real."""
    from src.features.engineering import compute_features
    return compute_features(sample_data)


@pytest.fixture
def sample_dataset(sample_features: pd.DataFrame):
    """
    (X, y, times) pronto para treino/inferencia.
    Usa prepare_dataset real do pipeline de producao.
    """
    from src.features.engineering import prepare_dataset
    X, y, times = prepare_dataset(sample_features)
    return X, y, times
