"""
Feature Experiment Engine.
Testa diferentes combinacoes de features automaticamente.
Treina, avalia e roda backtest para cada combinacao.
"""

import logging
import hashlib
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from src.models.registry import create_all_models

logger = logging.getLogger(__name__)

# Feature sets pre-definidos
FEATURE_SETS = {
    "technical": [
        "open", "high", "low", "close", "tick_volume",
        "return_simple", "return_log", "rsi_14",
        "ema_9", "ema_21", "ema_50", "ema_200",
        "atr_14", "vol_10", "vol_20",
        "spread_feature", "hour_sin", "hour_cos",
        "ema_50_200_diff", "ema_9_21_diff",
    ],
    "regime": [
        "trend", "volatility_regime", "momentum", "range_flag",
    ],
    "news": [
        "news_sentiment_base", "news_sentiment_quote",
        "news_impact_base", "news_impact_quote",
        "news_llm_sentiment_base", "news_llm_sentiment_quote",
        "news_volatility_base", "news_volatility_quote",
        "minutes_since_last_news", "minutes_to_next_news",
        "high_impact_flag",
        "news_sentiment_final_base", "news_sentiment_final_quote",
    ],
}

# Combinacoes a testar
EXPERIMENT_CONFIGS = [
    ["technical"],
    ["technical", "regime"],
    ["technical", "news"],
    ["technical", "regime", "news"],
]


def _get_feature_columns(feature_set_names: list[str]) -> list[str]:
    """Retorna colunas de features para um conjunto de nomes."""
    cols = []
    for name in feature_set_names:
        cols.extend(FEATURE_SETS.get(name, []))
    return cols


def _experiment_id(symbol: str, feature_set: list[str], model_name: str) -> str:
    """Gera ID unico para um experimento."""
    key = f"{symbol}_{'-'.join(sorted(feature_set))}_{model_name}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def run_feature_experiments(
    symbol: str,
    feature_configs: list[list[str]] = None,
    force: bool = False,
) -> pd.DataFrame:
    """
    Executa experimentos de features para um simbolo.

    Para cada combinacao de features:
    1. Monta dataset com features selecionadas
    2. Treina cada modelo
    3. Gera previsoes
    4. Avalia (accuracy, MAE)
    5. Roda backtest

    Args:
        symbol: simbolo para testar
        feature_configs: lista de combinacoes (default: EXPERIMENT_CONFIGS)
        force: re-rodar mesmo se ja existe resultado

    Returns:
        DataFrame com resultados de todos os experimentos
    """
    feature_configs = feature_configs or EXPERIMENT_CONFIGS
    exp_dir = settings.data_dir / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    cache_file = exp_dir / "results.parquet"

    # Carregar cache
    cached = pd.DataFrame()
    if cache_file.exists() and not force:
        cached = pd.read_parquet(cache_file)

    # Carregar dados do simbolo
    features_file = settings.features_dir / f"{symbol}.parquet"
    raw_file = settings.raw_dir / f"{symbol}.parquet"

    if not features_file.exists() or not raw_file.exists():
        logger.warning(f"{symbol}: sem dados para experimentos")
        return cached

    featured_df = pd.read_parquet(features_file)

    results = []

    for fs_names in feature_configs:
        feature_cols = _get_feature_columns(fs_names)
        available_cols = [c for c in feature_cols if c in featured_df.columns]

        if len(available_cols) < 3:
            logger.warning(f"{symbol}: poucas features disponiveis para {fs_names}")
            continue

        feature_set_label = "+".join(fs_names)

        # Verificar cache
        if not force and not cached.empty:
            existing = cached[
                (cached["symbol"] == symbol) &
                (cached["feature_set"] == feature_set_label)
            ]
            if not existing.empty:
                logger.info(f"{symbol}/{feature_set_label}: usando cache")
                continue

        # Preparar dataset com features selecionadas
        X, y, times = _prepare_filtered_dataset(featured_df, available_cols)
        if len(X) < 50:
            logger.warning(f"{symbol}/{feature_set_label}: dados insuficientes ({len(X)})")
            continue

        # Split temporal 80/20
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        # Treinar e avaliar cada modelo
        models = create_all_models()
        for model in models:
            try:
                model.fit(X_train, y_train)
                preds = model.predict(X_test)

                # Metricas de previsao
                accuracy = _direction_accuracy(y_test, preds, X_test)
                mae = float(np.mean(np.abs(preds - y_test)))

                # Backtest simulado
                bt_result = _quick_backtest(
                    preds, y_test, X_test, symbol,
                )

                results.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "symbol": symbol,
                    "feature_set": feature_set_label,
                    "feature_count": len(available_cols),
                    "model": model.name,
                    "accuracy": round(accuracy, 4),
                    "mae": round(mae, 8),
                    "pnl": bt_result.get("pnl_total", 0),
                    "sharpe": bt_result.get("sharpe", 0),
                    "drawdown": bt_result.get("max_drawdown", 0),
                    "winrate": bt_result.get("winrate", 0),
                    "total_trades": bt_result.get("total_trades", 0),
                    "train_size": split,
                    "test_size": len(X_test),
                })

                logger.info(
                    f"{symbol}/{feature_set_label}/{model.name}: "
                    f"acc={accuracy:.1f}% pnl={bt_result.get('pnl_total', 0):.1f} "
                    f"sharpe={bt_result.get('sharpe', 0):.2f}"
                )

            except Exception as e:
                logger.error(f"{symbol}/{feature_set_label}/{model.name}: {e}")

    # Salvar resultados
    if results:
        new_df = pd.DataFrame(results)
        if not cached.empty:
            combined = pd.concat([cached, new_df], ignore_index=True)
        else:
            combined = new_df
        combined.to_parquet(cache_file, index=False)
        return combined

    return cached


def run_all_experiments(
    symbols: list[str] = None,
    force: bool = False,
) -> pd.DataFrame:
    """Roda experimentos para todos os simbolos."""
    from src.mt5.symbols import DESIRED_SYMBOLS

    symbols = symbols or DESIRED_SYMBOLS
    all_results = []

    for symbol in symbols:
        try:
            result = run_feature_experiments(symbol, force=force)
            if not result.empty:
                all_results.append(result)
        except Exception as e:
            logger.error(f"Experimento falhou para {symbol}: {e}")

    if all_results:
        return pd.concat(all_results, ignore_index=True).drop_duplicates(
            subset=["symbol", "feature_set", "model"], keep="last"
        )
    return pd.DataFrame()


def get_experiment_results() -> pd.DataFrame:
    """Carrega resultados de experimentos salvos."""
    cache_file = settings.data_dir / "experiments" / "results.parquet"
    if not cache_file.exists():
        return pd.DataFrame()
    return pd.read_parquet(cache_file)


def _prepare_filtered_dataset(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> tuple:
    """Prepara dataset usando apenas features selecionadas."""
    input_window = settings.input_window
    output_horizon = settings.output_horizon

    all_cols = list(dict.fromkeys(feature_cols + ["close", "time"]))
    feature_df = df[all_cols].dropna().reset_index(drop=True)

    if len(feature_df) < input_window + output_horizon:
        return np.array([]), np.array([]), pd.DatetimeIndex([])

    X_list, y_list, times_list = [], [], []

    for i in range(input_window, len(feature_df) - output_horizon + 1):
        window = feature_df[feature_cols].iloc[i - input_window:i].values
        X_list.append(window.flatten())
        y_list.append(feature_df["close"].iloc[i:i + output_horizon].values.flatten())
        times_list.append(feature_df["time"].iloc[i])

    X = np.nan_to_num(np.array(X_list, dtype=np.float64))
    y = np.nan_to_num(np.array(y_list, dtype=np.float64))

    return X, y, pd.DatetimeIndex(times_list)


def _direction_accuracy(y_true, y_pred, X_test) -> float:
    """Calcula accuracy direcional."""
    if len(y_true) == 0:
        return 0.0

    # Usar ultimo close do input como referencia
    # O ultimo close esta na posicao que corresponde ao 'close' no flattened input
    # Simplificacao: comparar direcao t+1 predicted vs actual
    pred_dir = np.sign(y_pred[:, 0] - y_true[:, 0] + y_pred[:, 0])  # simplificado
    # Melhor approach: comparar se subiu ou desceu
    if y_true.shape[1] >= 1 and y_pred.shape[1] >= 1:
        # Direcao: pred > current vs actual > current
        # Aproximacao: usar y_true[i-1] como referencia
        actual_dir = np.sign(np.diff(y_true[:, 0], prepend=y_true[0, 0]))
        pred_dir = np.sign(np.diff(y_pred[:, 0], prepend=y_pred[0, 0]))
        correct = (actual_dir == pred_dir).sum()
        return float(correct / len(actual_dir) * 100)

    return 50.0


def _quick_backtest(
    predictions: np.ndarray,
    actuals: np.ndarray,
    X_test: np.ndarray,
    symbol: str,
) -> dict:
    """Backtest rapido inline (sem salvar)."""
    from src.mt5.symbols import get_pip_value

    pip_value = get_pip_value(symbol)
    spread = DEFAULT_SPREADS.get(symbol, 2.0) * pip_value

    pnl_list = []

    for i in range(len(predictions)):
        pred_close = predictions[i, 0]  # t+1
        actual_close = actuals[i, 0]    # t+1 real

        # Estimar preco atual (close anterior)
        if i > 0:
            current = actuals[i - 1, 0]
        else:
            current = actual_close

        ret = (pred_close - current) / current if current > 0 else 0

        if abs(ret) < 0.0003:
            continue  # HOLD

        if ret > 0:  # BUY
            pnl = (actual_close - current - spread) / pip_value
        else:  # SELL
            pnl = (current - actual_close - spread) / pip_value

        pnl_list.append(pnl)

    if not pnl_list:
        return {"pnl_total": 0, "sharpe": 0, "max_drawdown": 0, "winrate": 0, "total_trades": 0}

    pnl_arr = np.array(pnl_list)
    cumulative = np.cumsum(pnl_arr)
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak

    wins = (pnl_arr > 0).sum()
    returns = pnl_arr / 100  # normalize

    return {
        "pnl_total": round(float(cumulative[-1]), 2),
        "sharpe": round(float(np.mean(returns) / np.std(returns) * np.sqrt(288 * 252)) if np.std(returns) > 0 else 0, 4),
        "max_drawdown": round(float(np.min(drawdown)), 2),
        "winrate": round(float(wins / len(pnl_arr) * 100), 2),
        "total_trades": len(pnl_arr),
    }


# Spread defaults (duplicado do backtest engine para evitar import circular)
DEFAULT_SPREADS = {
    "EURUSD": 1.2, "GBPUSD": 1.5, "USDJPY": 1.3, "USDCHF": 1.5,
    "AUDUSD": 1.4, "USDCAD": 1.6, "NZDUSD": 1.8, "EURGBP": 1.5,
    "EURJPY": 1.8, "GBPJPY": 2.5, "XAUUSD": 3.0,
}
