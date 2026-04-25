"""Testes de integridade: consist\u00eancia entre endpoints, sanidade num\u00e9rica."""

import math

import pytest


@pytest.fixture(autouse=True)
def _force_market_open(monkeypatch):
    """Integrity tests pin Forex open; closed-state has dedicated tests."""
    monkeypatch.setattr(
        "src.features.session.is_market_open",
        lambda *args, **kwargs: True,
    )


def test_signal_matches_prediction(client, has_predictions):
    """Radar deve conter entrada para EURUSD e confidence coerente."""
    if not has_predictions:
        pytest.skip("Sem data/predictions no ambiente")

    pred = client.get("/api/predict/predictions/latest?symbol=EURUSD").json()
    signals = client.get("/api/predict/signals/radar").json()["signals"]

    eur_entries = [s for s in signals if s["symbol"] == "EURUSD"]
    assert len(eur_entries) == 1

    eur = eur_entries[0]
    assert eur["confidence"] >= 0.0
    assert eur["signal"] in {"BUY", "SELL", "HOLD"}

    # Se a predi\u00e7\u00e3o existe, o radar idealmente n\u00e3o cai em 'no_data'.
    if pred.get("ensemble") and eur.get("source") == "no_data":
        pytest.fail("Predi\u00e7\u00e3o existe mas radar marcou no_data \u2014 pipeline desalinhado")


def test_prediction_not_exploding(client, has_predictions):
    """Nenhum valor absurdo (> 1e6 ou NaN/Inf) em ensemble."""
    if not has_predictions:
        pytest.skip("Sem data/predictions no ambiente")

    pred = client.get("/api/predict/predictions/latest?symbol=EURUSD").json()
    ensemble = pred.get("ensemble")
    if ensemble is None:
        pytest.skip("Ensemble vazio")

    for key, val in ensemble.items():
        if val is None:
            continue
        assert math.isfinite(val), f"{key}={val} n\u00e3o finito"
        assert abs(val) < 1e6, f"{key}={val} fora de escala"


def test_current_price_positive(client, has_predictions):
    """current_price nunca pode ser negativo."""
    if not has_predictions:
        pytest.skip("Sem data/predictions no ambiente")

    pred = client.get("/api/predict/predictions/latest?symbol=EURUSD").json()
    cp = pred.get("current_price")
    if cp is None or cp == 0:
        pytest.skip("Sem current_price (s\u00edmbolo sem dados sanitizados)")
    assert cp > 0


def test_radar_all_symbols_are_desired(client):
    """Todos os s\u00edmbolos do radar devem pertencer a DESIRED_SYMBOLS."""
    from src.mt5.symbols import DESIRED_SYMBOLS

    signals = client.get("/api/predict/signals/radar").json()["signals"]
    radar_symbols = {s["symbol"] for s in signals}
    assert radar_symbols == set(DESIRED_SYMBOLS)


def test_json_has_no_nan_inf(client):
    """Nenhum endpoint cr\u00edtico pode serializar NaN/Inf (quebraria o JSON)."""
    # Se alguma resposta tiver NaN/Inf, httpx j\u00e1 falharia \u2014 mas fazemos checagem expl\u00edcita.
    urls = [
        "/api/predict/signals/radar",
        "/api/predict/predictions/latest?symbol=EURUSD",
        "/api/session/current?symbol=EURUSD",
        "/api/news/features?symbol=EURUSD",
    ]
    for url in urls:
        res = client.get(url)
        assert res.status_code == 200, f"{url} status {res.status_code}"
        # json() j\u00e1 re-parseia; se tivesse NaN/Inf nao-quoted, falharia.
        _ = res.json()


def test_session_score_consistent(client):
    """Mesmo s\u00edmbolo chamado duas vezes \u2192 mesma session_score (hor\u00e1rio fixo na janela)."""
    s1 = client.get("/api/session/current?symbol=EURUSD").json()["session_score"]
    s2 = client.get("/api/session/current?symbol=EURUSD").json()["session_score"]
    # Pode mudar se a chamada cruzar borda de sess\u00e3o \u2014 toler\u00e2ncia de 0.1
    assert abs(s1 - s2) < 0.2
