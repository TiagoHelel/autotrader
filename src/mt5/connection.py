"""
Modulo de conexao com MetaTrader 5.
Gerencia inicializacao, login, desconexao e operacoes basicas de dados.
"""

import logging
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd

from config.settings import settings, MT5Config

logger = logging.getLogger(__name__)


class MT5ConnectionError(Exception):
    """Erro de conexao com o MetaTrader 5."""
    pass


class MT5Connection:
    """
    Gerencia a conexao com o MetaTrader 5.

    Uso:
        with MT5Connection() as conn:
            df = conn.get_candles("EURUSD", mt5.TIMEFRAME_M1, count=1000)
            info = conn.account_info()
    """

    # Mapeamento de timeframe string -> constante MT5
    TIMEFRAME_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
        "W1":  mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }

    def __init__(self, config: Optional[MT5Config] = None):
        self._config = config or settings.mt5
        self._connected = False
        self._logged_in = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def connect(self) -> None:
        """Inicializa o terminal MT5 e faz login."""
        if self._connected:
            logger.warning("MT5 ja esta conectado.")
            return

        logger.info("Inicializando MT5...")
        if not mt5.initialize():
            error = mt5.last_error()
            raise MT5ConnectionError(f"Falha ao inicializar MT5: {error}")

        self._connected = True
        logger.info("MT5 inicializado com sucesso.")

        # Login
        logger.info(f"Logando na conta {self._config.account} @ {self._config.server}...")
        if not mt5.login(
            self._config.account,
            password=self._config.password,
            server=self._config.server,
        ):
            error = mt5.last_error()
            self.disconnect()
            raise MT5ConnectionError(f"Falha no login MT5: {error}")

        self._logged_in = True
        logger.info("Login MT5 OK.")

    def disconnect(self) -> None:
        """Desconecta do terminal MT5."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            self._logged_in = False
            logger.info("MT5 desconectado.")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._logged_in

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise MT5ConnectionError("MT5 nao esta conectado. Use connect() ou context manager.")

    # -------------------------------------------------------------------------
    # Account
    # -------------------------------------------------------------------------

    def account_info(self) -> dict:
        """Retorna informacoes da conta como dicionario."""
        self._ensure_connected()
        info = mt5.account_info()
        if info is None:
            raise MT5ConnectionError(f"Falha ao obter info da conta: {mt5.last_error()}")
        return {
            "login": info.login,
            "name": info.name,
            "server": info.server,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
            "leverage": info.leverage,
            "currency": info.currency,
            "profit": info.profit,
        }

    def terminal_info(self) -> dict:
        """Retorna informacoes do terminal MT5."""
        self._ensure_connected()
        info = mt5.terminal_info()
        if info is None:
            raise MT5ConnectionError(f"Falha ao obter info do terminal: {mt5.last_error()}")
        return {
            "name": info.name,
            "build": info.build,
            "path": info.path,
            "connected": info.connected,
            "trade_allowed": info.trade_allowed,
        }

    # -------------------------------------------------------------------------
    # Symbol info
    # -------------------------------------------------------------------------

    def symbol_info(self, symbol: str) -> dict:
        """Retorna informacoes do simbolo."""
        self._ensure_connected()

        # Garante que o simbolo esta visivel no Market Watch
        if not mt5.symbol_select(symbol, True):
            raise MT5ConnectionError(f"Falha ao selecionar simbolo {symbol}: {mt5.last_error()}")

        info = mt5.symbol_info(symbol)
        if info is None:
            raise MT5ConnectionError(f"Simbolo {symbol} nao encontrado: {mt5.last_error()}")

        return {
            "name": info.name,
            "description": info.description,
            "bid": info.bid,
            "ask": info.ask,
            "spread": info.spread,
            "digits": info.digits,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_mode": info.trade_mode,
        }

    def get_tick(self, symbol: str) -> dict:
        """Retorna o ultimo tick do simbolo."""
        self._ensure_connected()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise MT5ConnectionError(f"Falha ao obter tick de {symbol}: {mt5.last_error()}")
        return {
            "time": datetime.fromtimestamp(tick.time),
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
        }

    # -------------------------------------------------------------------------
    # Candles / Rates
    # -------------------------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        timeframe: str | int = "M1",
        count: int = 1000,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Retorna candles como DataFrame.

        Args:
            symbol: Simbolo MT5 (ex: "EURUSD")
            timeframe: String ("M1","M5",...) ou constante MT5
            count: Numero de candles (usado se date_from/date_to nao especificados)
            date_from: Data inicial (se especificada, usa copy_rates_range)
            date_to: Data final (se especificada junto com date_from)

        Returns:
            DataFrame com colunas: time, open, high, low, close, tick_volume, spread, real_volume
        """
        self._ensure_connected()

        # Resolve timeframe
        if isinstance(timeframe, str):
            tf = self.TIMEFRAME_MAP.get(timeframe.upper())
            if tf is None:
                raise ValueError(f"Timeframe invalido: {timeframe}. Use: {list(self.TIMEFRAME_MAP.keys())}")
        else:
            tf = timeframe

        # Garante simbolo visivel
        if not mt5.symbol_select(symbol, True):
            raise MT5ConnectionError(f"Falha ao selecionar simbolo {symbol}")

        # Busca candles
        if date_from and date_to:
            rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
        elif date_from:
            rates = mt5.copy_rates_from(symbol, tf, date_from, count)
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.warning(f"Nenhum candle retornado para {symbol} {timeframe}: {error}")
            return pd.DataFrame()

        # Converte para DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={
            "tick_volume": "tick_volume",
            "real_volume": "real_volume",
        }, inplace=True)

        logger.info(f"{symbol} {timeframe}: {len(df)} candles carregados "
                     f"({df['time'].iloc[0]} -> {df['time'].iloc[-1]})")
        return df

    def get_candles_bulk(
        self,
        symbols: list[str],
        timeframe: str = "M1",
        count: int = 1000,
    ) -> dict[str, pd.DataFrame]:
        """
        Retorna candles de multiplos simbolos.

        Returns:
            Dict {symbol: DataFrame}
        """
        result = {}
        for symbol in symbols:
            try:
                df = self.get_candles(symbol, timeframe, count)
                if not df.empty:
                    result[symbol] = df
            except MT5ConnectionError as e:
                logger.error(f"Erro ao buscar {symbol}: {e}")
        return result

    # -------------------------------------------------------------------------
    # Symbols listing
    # -------------------------------------------------------------------------

    def get_available_symbols(self, group: str = "*USD*") -> list[str]:
        """Lista simbolos disponiveis que correspondem ao grupo."""
        self._ensure_connected()
        symbols = mt5.symbols_get(group=group)
        if symbols is None:
            return []
        return [s.name for s in symbols]
