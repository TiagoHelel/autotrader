"""
Coleta de dados M5 do MetaTrader 5.
Salva em /data/raw/{symbol}.parquet com append incremental.
"""

import logging
from pathlib import Path

import pandas as pd

from config.settings import settings
from src.mt5.connection import MT5Connection
from src.mt5.symbols import DESIRED_SYMBOLS, FALLBACK_SYMBOLS

logger = logging.getLogger(__name__)


def validate_symbols(conn: MT5Connection, desired: list[str] = None) -> list[str]:
    """
    Valida simbolos desejados contra o broker.
    Completa com fallbacks ate cobrir todos os simbolos desejados.
    """
    desired = desired or DESIRED_SYMBOLS.copy()
    target_count = len(desired)
    valid = []

    # Tenta simbolos desejados
    available = conn.get_available_symbols(group="*")
    available_set = set(available)

    for symbol in desired:
        if symbol in available_set:
            valid.append(symbol)
        else:
            logger.warning(f"Simbolo {symbol} nao disponivel no broker")

    # Completa com fallbacks
    if len(valid) < target_count:
        for symbol in FALLBACK_SYMBOLS:
            if symbol in available_set and symbol not in valid:
                valid.append(symbol)
                logger.info(f"Adicionado fallback: {symbol}")
                if len(valid) >= target_count:
                    break

    # Se ainda falta, pega qualquer forex disponivel
    if len(valid) < target_count:
        for symbol in available:
            if symbol not in valid and len(symbol) == 6:
                valid.append(symbol)
                logger.info(f"Adicionado extra: {symbol}")
                if len(valid) >= target_count:
                    break

    logger.info(f"Simbolos validados ({len(valid)}): {valid}")
    return valid


def collect_initial(conn: MT5Connection, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """
    Coleta inicial de candles M5 (minimo 500 por simbolo).
    Salva em /data/raw/{symbol}.parquet.
    """
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    for symbol in symbols:
        try:
            df = conn.get_candles(
                symbol,
                timeframe=settings.timeframe,
                count=settings.min_candles,
            )
            if df.empty:
                logger.warning(f"{symbol}: nenhum candle retornado")
                continue

            filepath = raw_dir / f"{symbol}.parquet"
            df.to_parquet(filepath, index=False)
            result[symbol] = df
            logger.info(f"{symbol}: {len(df)} candles salvos em {filepath}")

        except Exception as e:
            logger.error(f"{symbol}: erro na coleta - {e}")

    return result


def collect_update(conn: MT5Connection, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """
    Atualiza dados existentes com novos candles (append incremental).
    Retorna dict com DataFrames atualizados.
    """
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    for symbol in symbols:
        try:
            filepath = raw_dir / f"{symbol}.parquet"

            # Carrega existente
            if filepath.exists():
                existing = pd.read_parquet(filepath)
                last_time = existing["time"].max()
                # Pega candles novos (com overlap de 5 para seguranca)
                new_df = conn.get_candles(
                    symbol,
                    timeframe=settings.timeframe,
                    count=50,
                )
                if new_df.empty:
                    result[symbol] = existing
                    continue

                # Merge sem duplicatas
                combined = pd.concat([existing, new_df], ignore_index=True)
                combined = combined.drop_duplicates(subset=["time"], keep="last")
                combined = combined.sort_values("time").reset_index(drop=True)
            else:
                # Primeira coleta
                combined = conn.get_candles(
                    symbol,
                    timeframe=settings.timeframe,
                    count=settings.min_candles,
                )

            if not combined.empty:
                combined.to_parquet(filepath, index=False)
                result[symbol] = combined
                logger.info(f"{symbol}: atualizado -> {len(combined)} candles")

        except Exception as e:
            logger.error(f"{symbol}: erro na atualizacao - {e}")

    return result


def load_raw(symbol: str) -> pd.DataFrame:
    """Carrega dados raw de um simbolo."""
    filepath = settings.raw_dir / f"{symbol}.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)
