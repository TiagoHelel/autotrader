"""
Cliente HTTP que fala com `mt5_api` (servidor FastAPI rodando na maquina
com terminal MT5). Implementa a mesma interface publica do
`MT5Connection` para ser drop-in replacement em consumidores que recebem
`conn` por parametro (`collect_*`, `engine.run_cycle`, etc.).

Uso:
    with MT5RemoteClient() as conn:
        df = conn.get_candles("EURUSD", "M1", count=1000)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from config.settings import settings, MT5Config

logger = logging.getLogger(__name__)


class MT5RemoteError(Exception):
    """Erro de comunicacao com o servidor mt5_api."""


class MT5RemoteClient:
    """Cliente HTTP com a mesma interface do `MT5Connection` (subset usado)."""

    def __init__(
        self,
        config: Optional[MT5Config] = None,
        timeout: float = 30.0,
    ) -> None:
        self._config = config or settings.mt5
        self._base_url = self._config.api_url.rstrip("/")
        self._token = self._config.api_token
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._connected = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def __enter__(self) -> "MT5RemoteClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.disconnect()
        return False

    def connect(self) -> None:
        """Abre client HTTP e valida via /health."""
        if self._connected:
            logger.warning("MT5RemoteClient ja esta conectado.")
            return

        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

        # Health check (sem auth) confirma que o servidor esta de pe.
        try:
            r = self._client.get("/health")
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self._client.close()
            self._client = None
            raise MT5RemoteError(
                f"Falha ao alcancar mt5_api em {self._base_url}: {e}"
            ) from e

        if not data.get("connected"):
            self._client.close()
            self._client = None
            raise MT5RemoteError(
                f"mt5_api respondeu mas nao esta conectado ao MT5: {data}"
            )

        self._connected = True
        logger.info("MT5RemoteClient conectado em %s", self._base_url)

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        if not self.is_connected:
            raise MT5RemoteError("MT5RemoteClient nao esta conectado.")
        try:
            r = self._client.get(path, params=params)  # type: ignore[union-attr]
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise MT5RemoteError(
                f"HTTP {e.response.status_code} em {path}: {e.response.text}"
            ) from e
        except httpx.HTTPError as e:
            raise MT5RemoteError(f"Falha de rede em {path}: {e}") from e

    # -------------------------------------------------------------------------
    # Account / terminal
    # -------------------------------------------------------------------------

    def account_info(self) -> dict:
        return self._get("/account")

    def terminal_info(self) -> dict:
        return self._get("/terminal")

    # -------------------------------------------------------------------------
    # Symbols
    # -------------------------------------------------------------------------

    def get_available_symbols(self, group: str = "*USD*") -> list[str]:
        data = self._get("/symbols", params={"group": group})
        return data.get("symbols", [])

    def symbol_info(self, symbol: str) -> dict:
        return self._get(f"/symbols/{symbol}")

    def get_tick(self, symbol: str) -> dict:
        data = self._get(f"/symbols/{symbol}/tick")
        # Servidor envia ISO; converte de volta pra datetime para casar
        # com a interface do MT5Connection.
        time_str = data.get("time")
        if isinstance(time_str, str):
            data["time"] = datetime.fromisoformat(time_str)
        return data

    # -------------------------------------------------------------------------
    # Candles
    # -------------------------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        timeframe: str | int = "M1",
        count: int = 1000,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if not isinstance(timeframe, str):
            raise ValueError(
                "MT5RemoteClient nao aceita timeframe numerico (use 'M1', 'M5'...)."
            )

        params: dict = {"tf": timeframe, "count": count}
        if date_from is not None:
            params["date_from"] = date_from.isoformat()
        if date_to is not None:
            params["date_to"] = date_to.isoformat()

        data = self._get(f"/candles/{symbol}", params=params)
        records = data.get("candles", [])
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["time"] = pd.to_datetime(df["time"])
        return df

    def get_candles_bulk(
        self,
        symbols: list[str],
        timeframe: str = "M1",
        count: int = 1000,
    ) -> dict[str, pd.DataFrame]:
        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                df = self.get_candles(symbol, timeframe, count)
                if not df.empty:
                    result[symbol] = df
            except MT5RemoteError as e:
                logger.error("Erro ao buscar %s: %s", symbol, e)
        return result
