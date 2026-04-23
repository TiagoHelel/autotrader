"""
Regime de mercado.
Classifica o estado atual do mercado: trend, volatilidade, momentum, range.
"""

import numpy as np
import pandas as pd


def compute_market_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera features de regime de mercado a partir de candles com features tecnicas.

    Requer colunas: close, ema_50, ema_200, atr_14, vol_20

    Retorna df com colunas adicionais:
    - trend: 1 (bull), -1 (bear)
    - volatility_regime: 0 (baixo), 1 (medio), 2 (alto)
    - momentum: retorno acumulado ultimos 10 candles
    - range_flag: 1 se mercado lateral, 0 caso contrario
    """
    df = df.copy()

    # 1. Trend: EMA50 vs EMA200
    if "ema_50" in df.columns and "ema_200" in df.columns:
        df["trend"] = np.where(df["ema_50"] > df["ema_200"], 1, -1)
    else:
        df["trend"] = 0

    # 2. Volatility regime: std_20 normalizada em percentis
    if "vol_20" in df.columns:
        vol = df["vol_20"]
        q33 = vol.quantile(0.33)
        q66 = vol.quantile(0.66)
        df["volatility_regime"] = np.where(
            vol <= q33, 0,
            np.where(vol <= q66, 1, 2)
        )
    else:
        df["volatility_regime"] = 1

    # 3. Momentum: retorno acumulado ultimos 10 candles
    df["momentum"] = df["close"].pct_change(periods=10)

    # 4. Range flag: ATR baixo + baixa variacao de preco
    if "atr_14" in df.columns:
        atr_median = df["atr_14"].rolling(50, min_periods=10).median()
        price_range = (df["high"].rolling(10).max() - df["low"].rolling(10).min())
        price_range_median = price_range.rolling(50, min_periods=10).median()

        atr_low = df["atr_14"] < atr_median * 0.8
        range_low = price_range < price_range_median * 0.8

        df["range_flag"] = np.where(atr_low & range_low, 1, 0)
    else:
        df["range_flag"] = 0

    # Preenche NaN com valores neutros
    df["trend"] = df["trend"].fillna(0).astype(int)
    df["volatility_regime"] = df["volatility_regime"].fillna(1).astype(int)
    df["momentum"] = df["momentum"].fillna(0.0)
    df["range_flag"] = df["range_flag"].fillna(0).astype(int)

    return df


def get_current_regime(df: pd.DataFrame) -> dict:
    """Retorna o regime atual (ultima linha) como dicionario."""
    if df.empty:
        return {
            "trend": 0,
            "volatility_regime": 1,
            "momentum": 0.0,
            "range_flag": 0,
        }
    last = df.iloc[-1]
    return {
        "trend": int(last.get("trend", 0)),
        "trend_label": "bull" if last.get("trend", 0) == 1 else "bear",
        "volatility_regime": int(last.get("volatility_regime", 1)),
        "volatility_label": ["low", "medium", "high"][int(last.get("volatility_regime", 1))],
        "momentum": float(last.get("momentum", 0.0)),
        "range_flag": int(last.get("range_flag", 0)),
        "range_label": "ranging" if last.get("range_flag", 0) == 1 else "trending",
    }
