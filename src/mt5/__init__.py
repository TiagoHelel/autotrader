"""Pacote MT5: conexao local via lib `MetaTrader5` ou remota via mt5_api."""

from __future__ import annotations

import logging
from typing import Union

from config.settings import settings

from .connection import MT5Connection, MT5ConnectionError
from .remote_client import MT5RemoteClient, MT5RemoteError
from .symbols import DESIRED_SYMBOLS, SYMBOL_CONFIG

logger = logging.getLogger(__name__)

MT5Conn = Union[MT5Connection, MT5RemoteClient]


def get_mt5_connection() -> MT5Conn:
    """
    Factory: retorna `MT5Connection` (local) ou `MT5RemoteClient` (HTTP)
    de acordo com `settings.mt5.backend`. Default: local.
    """
    backend = settings.mt5.backend
    if backend == "remote":
        logger.info("MT5 backend: remote (%s)", settings.mt5.api_url)
        return MT5RemoteClient()
    if backend != "local":
        logger.warning("MT5_BACKEND='%s' nao reconhecido; usando local.", backend)
    logger.info("MT5 backend: local")
    return MT5Connection()


__all__ = [
    "MT5Connection",
    "MT5ConnectionError",
    "MT5RemoteClient",
    "MT5RemoteError",
    "DESIRED_SYMBOLS",
    "SYMBOL_CONFIG",
    "get_mt5_connection",
]
