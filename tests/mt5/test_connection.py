"""
Tests for src/mt5/connection.py — MT5Connection com mock do MetaTrader5.

Estratégia: mock completo do módulo MetaTrader5 (não está instalado em CI).
Testa contrato: connect/disconnect lifecycle, context manager, get_candles,
account_info, error handling.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest


# MT5Connection importa MetaTrader5 as mt5 no topo. Precisamos
# substituir a referência já importada dentro do módulo.
@pytest.fixture(autouse=True)
def mock_mt5():
    """Mock global do módulo MetaTrader5 dentro de connection.py."""
    mock = MagicMock()
    # Constantes de timeframe
    mock.TIMEFRAME_M1 = 1
    mock.TIMEFRAME_M5 = 5
    mock.TIMEFRAME_M15 = 15
    mock.TIMEFRAME_M30 = 30
    mock.TIMEFRAME_H1 = 60
    mock.TIMEFRAME_H4 = 240
    mock.TIMEFRAME_D1 = 1440
    mock.TIMEFRAME_W1 = 10080
    mock.TIMEFRAME_MN1 = 43200
    with patch("src.mt5.connection.mt5", mock):
        yield mock


@pytest.fixture
def mt5_module(mock_mt5):
    """Retorna o mock do MT5 já configurado para sucesso."""
    mock_mt5.initialize.return_value = True
    mock_mt5.login.return_value = True
    mock_mt5.symbol_select.return_value = True
    return mock_mt5


@pytest.fixture
def conn(mt5_module):
    """MT5Connection conectada."""
    from src.mt5.connection import MT5Connection
    c = MT5Connection()
    c.connect()
    return c


class TestLifecycle:
    def test_connect_success(self, mt5_module):
        from src.mt5.connection import MT5Connection
        c = MT5Connection()
        c.connect()
        assert c.is_connected
        mt5_module.initialize.assert_called_once()
        mt5_module.login.assert_called_once()

    def test_connect_init_failure(self, mt5_module):
        from src.mt5.connection import MT5Connection, MT5ConnectionError
        mt5_module.initialize.return_value = False
        mt5_module.last_error.return_value = (-1, "init failed")
        with pytest.raises(MT5ConnectionError, match="Falha ao inicializar"):
            MT5Connection().connect()

    def test_connect_login_failure(self, mt5_module):
        from src.mt5.connection import MT5Connection, MT5ConnectionError
        mt5_module.login.return_value = False
        mt5_module.last_error.return_value = (-2, "login failed")
        with pytest.raises(MT5ConnectionError, match="Falha no login"):
            MT5Connection().connect()

    def test_disconnect(self, conn, mt5_module):
        conn.disconnect()
        assert not conn.is_connected
        mt5_module.shutdown.assert_called_once()

    def test_double_connect_warns(self, conn, mt5_module, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        conn.connect()
        assert any("ja esta conectado" in r.message for r in caplog.records)

    def test_context_manager(self, mt5_module):
        from src.mt5.connection import MT5Connection
        with MT5Connection() as c:
            assert c.is_connected
        mt5_module.shutdown.assert_called_once()


class TestEnsureConnected:
    def test_raises_when_not_connected(self, mt5_module):
        from src.mt5.connection import MT5Connection, MT5ConnectionError
        c = MT5Connection()
        with pytest.raises(MT5ConnectionError, match="nao esta conectado"):
            c.account_info()


class TestAccountInfo:
    def test_success(self, conn, mt5_module):
        mt5_module.account_info.return_value = SimpleNamespace(
            login=12345, name="Test", server="Demo",
            balance=10000.0, equity=10000.0, margin=0.0,
            margin_free=10000.0, leverage=100, currency="USD", profit=0.0,
        )
        info = conn.account_info()
        assert info["balance"] == 10000.0
        assert info["login"] == 12345

    def test_failure(self, conn, mt5_module):
        from src.mt5.connection import MT5ConnectionError
        mt5_module.account_info.return_value = None
        mt5_module.last_error.return_value = (-3, "no info")
        with pytest.raises(MT5ConnectionError):
            conn.account_info()


class TestTerminalInfo:
    def test_success(self, conn, mt5_module):
        mt5_module.terminal_info.return_value = SimpleNamespace(
            name="MT5", build=3000, path="C:\\MT5",
            connected=True, trade_allowed=True,
        )
        info = conn.terminal_info()
        assert info["build"] == 3000

    def test_failure(self, conn, mt5_module):
        from src.mt5.connection import MT5ConnectionError
        mt5_module.terminal_info.return_value = None
        with pytest.raises(MT5ConnectionError):
            conn.terminal_info()


class TestSymbolInfo:
    def test_success(self, conn, mt5_module):
        mt5_module.symbol_info.return_value = SimpleNamespace(
            name="EURUSD", description="Euro vs USD",
            bid=1.1000, ask=1.1002, spread=2, digits=5,
            volume_min=0.01, volume_max=100.0, volume_step=0.01,
            trade_mode=0,
        )
        info = conn.symbol_info("EURUSD")
        assert info["name"] == "EURUSD"
        assert info["spread"] == 2

    def test_select_failure(self, conn, mt5_module):
        from src.mt5.connection import MT5ConnectionError
        mt5_module.symbol_select.return_value = False
        with pytest.raises(MT5ConnectionError, match="Falha ao selecionar"):
            conn.symbol_info("INVALID")


class TestGetTick:
    def test_success(self, conn, mt5_module):
        mt5_module.symbol_info_tick.return_value = SimpleNamespace(
            time=1700000000, bid=1.1000, ask=1.1002, last=0, volume=100,
        )
        tick = conn.get_tick("EURUSD")
        assert tick["bid"] == 1.1000

    def test_failure(self, conn, mt5_module):
        from src.mt5.connection import MT5ConnectionError
        mt5_module.symbol_info_tick.return_value = None
        with pytest.raises(MT5ConnectionError):
            conn.get_tick("EURUSD")


class TestGetCandles:
    def _make_rates(self, n=10):
        return np.array(
            [(1700000000 + i * 60, 1.1 + i * 0.0001, 1.1 + i * 0.0001 + 0.0002,
              1.1 + i * 0.0001 - 0.0001, 1.1 + (i + 1) * 0.0001, 100, 2, 0)
             for i in range(n)],
            dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                   ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8")],
        )

    def test_by_count(self, conn, mt5_module):
        mt5_module.copy_rates_from_pos.return_value = self._make_rates(5)
        df = conn.get_candles("EURUSD", "M1", count=5)
        assert len(df) == 5
        assert "time" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["time"])

    def test_by_date_range(self, conn, mt5_module):
        mt5_module.copy_rates_range.return_value = self._make_rates(3)
        df = conn.get_candles(
            "EURUSD", "M5",
            date_from=datetime(2025, 1, 1),
            date_to=datetime(2025, 1, 2),
        )
        assert len(df) == 3

    def test_by_date_from(self, conn, mt5_module):
        mt5_module.copy_rates_from.return_value = self._make_rates(2)
        df = conn.get_candles("EURUSD", "H1", date_from=datetime(2025, 1, 1))
        assert len(df) == 2

    def test_invalid_timeframe(self, conn):
        with pytest.raises(ValueError, match="Timeframe invalido"):
            conn.get_candles("EURUSD", "INVALID")

    def test_no_rates_returns_empty(self, conn, mt5_module):
        mt5_module.copy_rates_from_pos.return_value = None
        df = conn.get_candles("EURUSD", "M1")
        assert df.empty

    def test_int_timeframe(self, conn, mt5_module):
        mt5_module.copy_rates_from_pos.return_value = self._make_rates(2)
        df = conn.get_candles("EURUSD", 5, count=2)  # int timeframe
        assert len(df) == 2


class TestGetCandlesBulk:
    def test_multiple_symbols(self, conn, mt5_module):
        rates = np.array(
            [(1700000000, 1.1, 1.11, 1.09, 1.10, 100, 2, 0)],
            dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                   ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8")],
        )
        mt5_module.copy_rates_from_pos.return_value = rates
        result = conn.get_candles_bulk(["EURUSD", "GBPUSD"])
        assert "EURUSD" in result
        assert "GBPUSD" in result

    def test_error_in_one_symbol(self, conn, mt5_module):
        mt5_module.symbol_select.side_effect = [True, False, True]
        mt5_module.copy_rates_from_pos.return_value = np.array(
            [(1700000000, 1.1, 1.11, 1.09, 1.10, 100, 2, 0)],
            dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                   ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8")],
        )
        result = conn.get_candles_bulk(["EURUSD", "INVALID"])
        # EURUSD succeeds, INVALID fails silently
        assert "EURUSD" in result


class TestGetAvailableSymbols:
    def test_returns_names(self, conn, mt5_module):
        mt5_module.symbols_get.return_value = [
            SimpleNamespace(name="EURUSD"),
            SimpleNamespace(name="GBPUSD"),
        ]
        symbols = conn.get_available_symbols()
        assert symbols == ["EURUSD", "GBPUSD"]

    def test_none_returns_empty(self, conn, mt5_module):
        mt5_module.symbols_get.return_value = None
        assert conn.get_available_symbols() == []
