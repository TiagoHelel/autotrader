"""
Backtest Engine - Simulacao de PnL real.
Simula trades baseados em sinais, calcula metricas financeiras.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from src.mt5.symbols import get_pip_value

logger = logging.getLogger(__name__)

# Spread default em pips por tipo de simbolo
DEFAULT_SPREADS = {
    "EURUSD": 1.2, "GBPUSD": 1.5, "USDJPY": 1.3, "USDCHF": 1.5,
    "AUDUSD": 1.4, "USDCAD": 1.6, "NZDUSD": 1.8, "EURGBP": 1.5,
    "EURJPY": 1.8, "GBPJPY": 2.5, "XAUUSD": 3.0,
}


def run_backtest(
    predictions_df: pd.DataFrame,
    price_df: pd.DataFrame,
    symbol: str = "EURUSD",
    exit_horizon: int = 3,
    signal_threshold: float = 0.0003,
    spread_pips: float = None,
) -> dict:
    """
    Executa backtest simulando trades baseados em previsoes.

    Args:
        predictions_df: DataFrame com colunas [timestamp, model, current_price, pred_t1, pred_t2, pred_t3]
        price_df: DataFrame com candles [time, open, high, low, close]
        symbol: par de moedas
        exit_horizon: candles para fechar posicao (1 ou 3)
        signal_threshold: retorno minimo para abrir trade
        spread_pips: spread em pips (default: tabela)

    Returns:
        dict com resultados do backtest e trades simulados
    """
    pip_value = get_pip_value(symbol)
    spread = (spread_pips or DEFAULT_SPREADS.get(symbol, 2.0)) * pip_value

    price_df = price_df.sort_values("time").reset_index(drop=True)
    price_df["time"] = pd.to_datetime(price_df["time"])

    predictions_df = predictions_df.copy()
    predictions_df["timestamp"] = pd.to_datetime(predictions_df["timestamp"])

    trades = []

    for _, pred in predictions_df.iterrows():
        pred_time = pred["timestamp"]
        current_price = pred["current_price"]
        pred_t1 = pred.get("pred_t1", current_price)
        pred_t2 = pred.get("pred_t2", current_price)
        pred_t3 = pred.get("pred_t3", current_price)

        # Calcular retorno esperado
        ret = ((pred_t1 - current_price) * 0.5 +
               (pred_t2 - current_price) * 0.3 +
               (pred_t3 - current_price) * 0.2) / current_price if current_price > 0 else 0

        if abs(ret) < signal_threshold:
            continue  # HOLD - sem trade

        direction = "BUY" if ret > 0 else "SELL"

        # Encontrar candle de entrada (proximo candle apos previsao)
        future = price_df[price_df["time"] > pred_time]
        if len(future) < exit_horizon + 1:
            continue

        entry_price = future.iloc[0]["close"]
        exit_price = future.iloc[exit_horizon - 1]["close"]

        # Calcular PnL em pips
        if direction == "BUY":
            entry_with_spread = entry_price + spread / 2
            exit_with_spread = exit_price - spread / 2
            pnl_price = exit_with_spread - entry_with_spread
        else:
            entry_with_spread = entry_price - spread / 2
            exit_with_spread = exit_price + spread / 2
            pnl_price = entry_with_spread - exit_with_spread

        pnl_pips = pnl_price / pip_value

        trades.append({
            "timestamp": pred_time.isoformat(),
            "model": pred.get("model", "unknown"),
            "symbol": symbol,
            "direction": direction,
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "entry_time": future.iloc[0]["time"].isoformat(),
            "exit_time": future.iloc[exit_horizon - 1]["time"].isoformat(),
            "pnl_price": float(pnl_price),
            "pnl_pips": float(pnl_pips),
            "spread_cost": float(spread),
            "expected_return": float(ret),
            "exit_horizon": exit_horizon,
        })

    if not trades:
        return _empty_result(symbol)

    trades_df = pd.DataFrame(trades)
    metrics = _compute_metrics(trades_df)

    return {
        "symbol": symbol,
        "trades": trades,
        "trades_count": len(trades),
        "metrics": metrics,
    }


def run_backtest_by_model(
    symbol: str,
    exit_horizon: int = 3,
    signal_threshold: float = 0.0003,
) -> dict:
    """
    Roda backtest para todos os modelos de um simbolo usando dados salvos.

    Returns:
        {model_name: backtest_result}
    """
    pred_file = settings.predictions_dir / f"{symbol}.parquet"
    raw_file = settings.raw_dir / f"{symbol}.parquet"

    if not pred_file.exists() or not raw_file.exists():
        return {}

    pred_df = pd.read_parquet(pred_file)
    price_df = pd.read_parquet(raw_file)

    results = {}
    for model_name, model_preds in pred_df.groupby("model"):
        result = run_backtest(
            model_preds, price_df, symbol,
            exit_horizon=exit_horizon,
            signal_threshold=signal_threshold,
        )
        result["model"] = model_name
        results[model_name] = result

        # Salvar resultados
        _save_backtest(symbol, model_name, result)

    return results


def get_backtest_results(symbol: str = None, model: str = None) -> pd.DataFrame:
    """Carrega resultados de backtest salvos."""
    bt_dir = settings.data_dir / "backtest"
    if not bt_dir.exists():
        return pd.DataFrame()

    dfs = []
    pattern = f"{symbol}_*.parquet" if symbol else "*.parquet"
    for f in bt_dir.glob(pattern):
        df = pd.read_parquet(f)
        if model and "model" in df.columns:
            df = df[df["model"] == model]
        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


def get_backtest_summary() -> list[dict]:
    """Retorna resumo de backtest por modelo/simbolo."""
    bt_dir = settings.data_dir / "backtest"
    if not bt_dir.exists():
        return []

    summaries = []
    for f in bt_dir.glob("*_metrics.parquet"):
        df = pd.read_parquet(f)
        for _, row in df.iterrows():
            summaries.append(row.to_dict())

    return sorted(summaries, key=lambda x: x.get("pnl_total", 0), reverse=True)


def _compute_metrics(trades_df: pd.DataFrame) -> dict:
    """Calcula metricas financeiras a partir de trades."""
    pnl_series = trades_df["pnl_pips"].values

    # PnL acumulado
    cumulative_pnl = np.cumsum(pnl_series)
    pnl_total = float(cumulative_pnl[-1]) if len(cumulative_pnl) > 0 else 0

    # Retorno percentual acumulado
    pnl_price_series = trades_df["pnl_price"].values
    entries = trades_df["entry_price"].values
    returns = pnl_price_series / entries
    total_return_pct = float(np.sum(returns) * 100)

    # Win rate
    wins = (pnl_series > 0).sum()
    total = len(pnl_series)
    winrate = float(wins / total * 100) if total > 0 else 0

    # Max drawdown (em pips)
    peak = np.maximum.accumulate(cumulative_pnl)
    drawdown = cumulative_pnl - peak
    max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0

    # Sharpe ratio (anualizado, assumindo ~252 trading days, ~288 candles M5/dia)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(288 * 252))
    else:
        sharpe = 0.0

    # Profit factor
    gross_profit = float(pnl_series[pnl_series > 0].sum()) if (pnl_series > 0).any() else 0
    gross_loss = float(abs(pnl_series[pnl_series < 0].sum())) if (pnl_series < 0).any() else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

    # Equity curve
    equity_curve = cumulative_pnl.tolist()

    return {
        "pnl_total": round(pnl_total, 2),
        "return_pct": round(total_return_pct, 4),
        "winrate": round(winrate, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe": round(sharpe, 4),
        "profit_factor": round(profit_factor, 4),
        "total_trades": total,
        "winning_trades": int(wins),
        "losing_trades": int(total - wins),
        "avg_pnl": round(float(np.mean(pnl_series)), 4),
        "max_win": round(float(np.max(pnl_series)), 4) if total > 0 else 0,
        "max_loss": round(float(np.min(pnl_series)), 4) if total > 0 else 0,
        "equity_curve": equity_curve,
    }


def _save_backtest(symbol: str, model_name: str, result: dict) -> None:
    """Salva resultado de backtest em parquet."""
    bt_dir = settings.data_dir / "backtest"
    bt_dir.mkdir(parents=True, exist_ok=True)

    # Salvar trades
    if result.get("trades"):
        trades_df = pd.DataFrame(result["trades"])
        trades_file = bt_dir / f"{symbol}_{model_name}.parquet"
        trades_df.to_parquet(trades_file, index=False)

    # Salvar metricas
    if result.get("metrics"):
        metrics = {**result["metrics"]}
        metrics.pop("equity_curve", None)  # Nao salvar equity curve no parquet de metricas
        metrics["symbol"] = symbol
        metrics["model"] = model_name
        metrics["timestamp"] = datetime.utcnow().isoformat()

        metrics_file = bt_dir / f"{symbol}_{model_name}_metrics.parquet"
        pd.DataFrame([metrics]).to_parquet(metrics_file, index=False)

    logger.info(f"Backtest salvo: {symbol}/{model_name} - PnL={result.get('metrics', {}).get('pnl_total', 0):.2f} pips")


def _empty_result(symbol: str) -> dict:
    """Retorna resultado vazio de backtest."""
    return {
        "symbol": symbol,
        "trades": [],
        "trades_count": 0,
        "metrics": {
            "pnl_total": 0, "return_pct": 0, "winrate": 0,
            "max_drawdown": 0, "sharpe": 0, "profit_factor": 0,
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "avg_pnl": 0, "max_win": 0, "max_loss": 0, "equity_curve": [],
        },
    }
