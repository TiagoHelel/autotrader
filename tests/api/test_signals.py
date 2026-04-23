"""Testes do signal radar (`/api/predict/signals/radar`)."""

import pytest


VALID_SIGNALS = {"BUY", "SELL", "HOLD"}


def test_signal_radar(client):
    """Radar retorna payload com `signals` e 11 entries (DESIRED_SYMBOLS)."""
    res = client.get("/api/predict/signals/radar")
    assert res.status_code == 200

    data = res.json()
    assert "signals" in data
    assert isinstance(data["signals"], list)
    assert len(data["signals"]) == 11


def test_signal_fields(client):
    """Cada signal cont\u00e9m symbol, signal e confidence."""
    signals = client.get("/api/predict/signals/radar").json()["signals"]
    for s in signals:
        assert "symbol" in s
        assert "signal" in s
        assert "confidence" in s


def test_signal_values(client):
    """`signal` sempre em {BUY, SELL, HOLD}."""
    signals = client.get("/api/predict/signals/radar").json()["signals"]
    for s in signals:
        assert s["signal"] in VALID_SIGNALS


def test_signal_confidence_in_range(client):
    """Confidence deve estar em [0, 1] e ser finito."""
    import math
    signals = client.get("/api/predict/signals/radar").json()["signals"]
    for s in signals:
        c = s["confidence"]
        assert c is None or (math.isfinite(c) and 0.0 <= c <= 1.0)


def test_signal_breakdown_sums(client):
    """breakdown BUY+SELL+HOLD == total."""
    data = client.get("/api/predict/signals/radar").json()
    if "breakdown" not in data:
        pytest.skip("Endpoint sem breakdown opcional")

    b = data["breakdown"]
    total = data.get("total", len(data["signals"]))
    assert b["BUY"] + b["SELL"] + b["HOLD"] == total
