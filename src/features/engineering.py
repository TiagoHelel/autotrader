"""
Feature engineering para previsao M5.
Gera indicadores tecnicos, regime de mercado e prepara datasets para modelos.
"""

import logging

import numpy as np
import pandas as pd

from config.settings import settings
from src.features.regime import compute_market_regime
from src.features.session import SESSION_FEATURE_COLUMNS

logger = logging.getLogger(__name__)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera todas as features a partir do DataFrame de candles raw.

    Features geradas:
    - returns (log e simples)
    - RSI(14)
    - EMA(9, 21, 50, 200)
    - ATR(14)
    - rolling volatility (std 10, 20)
    - spread (se disponivel)
    - hora do dia (sin/cos encoding)
    """
    df = df.copy()
    df = df.sort_values("time").reset_index(drop=True)

    # Returns
    df["return_simple"] = df["close"].pct_change()
    df["return_log"] = np.log(df["close"] / df["close"].shift(1))

    # RSI(14)
    df["rsi_14"] = _rsi(df["close"], 14)

    # EMAs
    for period in [9, 21, 50, 200]:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()

    # ATR(14)
    df["atr_14"] = _atr(df, 14)

    # Rolling volatility
    df["vol_10"] = df["return_simple"].rolling(10).std()
    df["vol_20"] = df["return_simple"].rolling(20).std()

    # Spread (se disponivel)
    if "spread" in df.columns:
        df["spread_feature"] = df["spread"].astype(float)
    else:
        df["spread_feature"] = 0.0

    # Hora do dia (sin/cos encoding)
    if pd.api.types.is_datetime64_any_dtype(df["time"]):
        hour = df["time"].dt.hour + df["time"].dt.minute / 60.0
    else:
        df["time"] = pd.to_datetime(df["time"])
        hour = df["time"].dt.hour + df["time"].dt.minute / 60.0

    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

    # EMA cross features (para modelo heuristico)
    df["ema_50_200_diff"] = df["ema_50"] - df["ema_200"]
    df["ema_9_21_diff"] = df["ema_9"] - df["ema_21"]

    # Regime de mercado
    df = compute_market_regime(df)

    return df


def _rsi(series: pd.Series, period: int) -> pd.Series:
    """Calcula RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calcula ATR."""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        (high - low),
        (high - close).abs(),
        (low - close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# Colunas de features usadas como input dos modelos
FEATURE_COLUMNS = [
    "open", "high", "low", "close", "tick_volume",
    "return_simple", "return_log",
    "rsi_14",
    "ema_9", "ema_21", "ema_50", "ema_200",
    "atr_14",
    "vol_10", "vol_20",
    "spread_feature",
    "hour_sin", "hour_cos",
    "ema_50_200_diff", "ema_9_21_diff",
    # Regime features
    "trend", "volatility_regime", "momentum", "range_flag",
]

# Colunas de sessao (adicionadas dinamicamente pelo engine)
SESSION_FEATURE_COLUMNS_LIST = list(SESSION_FEATURE_COLUMNS)

# Colunas de news features (adicionadas dinamicamente pelo engine)
NEWS_FEATURE_COLUMNS = [
    "news_sentiment_base", "news_sentiment_quote",
    "news_impact_base", "news_impact_quote",
    "news_llm_sentiment_base", "news_llm_sentiment_quote",
    "news_volatility_base", "news_volatility_quote",
    "minutes_since_last_news",
    "high_impact_flag",
    "news_sentiment_final_base", "news_sentiment_final_quote",
]

# Todas as features (tecnicas + regime + sessao + news)
ALL_FEATURE_COLUMNS = FEATURE_COLUMNS + SESSION_FEATURE_COLUMNS_LIST + NEWS_FEATURE_COLUMNS


def prepare_dataset(
    df: pd.DataFrame,
    input_window: int = None,
    output_horizon: int = None,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Prepara dataset para treino/inferencia.

    Args:
        df: DataFrame com features computadas
        input_window: numero de candles de input (default: settings.input_window)
        output_horizon: numero de candles a prever (default: settings.output_horizon)

    Returns:
        X: array (n_samples, input_window * n_features)
        y: array (n_samples, output_horizon) - closes futuros
        times: timestamps correspondentes
    """
    input_window = input_window or settings.input_window
    output_horizon = output_horizon or settings.output_horizon

    # Determinar quais colunas de features estao disponiveis
    available_cols = [c for c in ALL_FEATURE_COLUMNS if c in df.columns]
    if not available_cols:
        available_cols = [c for c in FEATURE_COLUMNS if c in df.columns]

    # Remove NaN das features (avoid duplicating 'close' which is already in FEATURE_COLUMNS)
    extra_cols = [c for c in ["time"] if c not in available_cols]
    feature_df = df[available_cols + extra_cols].dropna()
    feature_df = feature_df.reset_index(drop=True)

    if len(feature_df) < input_window + output_horizon:
        logger.warning(f"Dados insuficientes: {len(feature_df)} < {input_window + output_horizon}")
        return np.array([]), np.array([]), pd.DatetimeIndex([])

    X_list = []
    y_list = []
    times_list = []

    for i in range(input_window, len(feature_df) - output_horizon + 1):
        # Input: janela de features (flattened)
        window = feature_df[available_cols].iloc[i - input_window:i].values
        X_list.append(window.flatten())

        # Output: proximos closes (use .values to get 1D array)
        future_closes = feature_df["close"].iloc[i:i + output_horizon]
        y_list.append(future_closes.values.flatten())

        times_list.append(feature_df["time"].iloc[i])

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.float64)

    # Substitui NaN/Inf por 0
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)

    times = pd.DatetimeIndex(times_list)

    return X, y, times


def prepare_inference_input(df: pd.DataFrame, input_window: int = None) -> np.ndarray:
    """
    Prepara input para inferencia (ultimos N candles).
    Retorna array (1, input_window * n_features).
    """
    input_window = input_window or settings.input_window

    available_cols = [c for c in ALL_FEATURE_COLUMNS if c in df.columns]
    if not available_cols:
        available_cols = [c for c in FEATURE_COLUMNS if c in df.columns]

    feature_df = df[available_cols].dropna()
    if len(feature_df) < input_window:
        logger.warning(f"Dados insuficientes para inferencia: {len(feature_df)} < {input_window}")
        return np.array([])

    window = feature_df.iloc[-input_window:].values.flatten()
    return np.nan_to_num(window, nan=0.0, posinf=0.0, neginf=0.0).reshape(1, -1)


def save_features(df: pd.DataFrame, symbol: str) -> None:
    """Salva dataset de features em parquet."""
    features_dir = settings.features_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    filepath = features_dir / f"{symbol}.parquet"
    df.to_parquet(filepath, index=False)
    logger.info(f"Features salvas: {filepath} ({len(df)} rows)")


def load_features(symbol: str) -> pd.DataFrame:
    """Carrega dataset de features."""
    filepath = settings.features_dir / f"{symbol}.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)
