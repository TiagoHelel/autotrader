"""Testes dos endpoints /api/predict/* (s\u00edmbolos, previs\u00f5es)."""

import pytest


def test_get_symbols(client):
    """`/api/predict/symbols` retorna lista (ou dict com 'symbols')."""
    res = client.get("/api/predict/symbols")
    assert res.status_code == 200

    data = res.json()
    # Endpoint pode retornar lista direta ou dict wrapper
    symbols = data if isinstance(data, list) else data.get("symbols", data)
    assert isinstance(symbols, list)


def test_latest_prediction(client, has_predictions):
    """`/api/predict/predictions/latest?symbol=EURUSD` retorna ensemble + models + confidence."""
    if not has_predictions:
        pytest.skip("Sem data/predictions/*.parquet no ambiente")

    res = client.get("/api/predict/predictions/latest?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert "ensemble" in data
    assert "confidence" in data
    assert "models" in data
    assert data["symbol"] == "EURUSD"


def test_prediction_shape(client, has_predictions):
    """Ensemble deve ter 3 horizontes: t+1, t+2, t+3."""
    if not has_predictions:
        pytest.skip("Sem data/predictions/*.parquet no ambiente")

    data = client.get("/api/predict/predictions/latest?symbol=EURUSD").json()
    ensemble = data["ensemble"]
    if ensemble is None:
        pytest.skip("Sem ensemble dispon\u00edvel (dados vazios ap\u00f3s sanitize)")

    # ensemble \u00e9 dict com pred_t1, pred_t2, pred_t3
    assert len(ensemble) == 3
    assert set(ensemble.keys()) == {"pred_t1", "pred_t2", "pred_t3"}


def test_predictions_list(client):
    """`/api/predict/predictions` deve retornar lista (ou dict wrapper)."""
    res = client.get("/api/predict/predictions?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, (list, dict))


def test_prediction_models_list(client, has_predictions):
    """`models` no payload deve ser uma lista de dicts com 'model'."""
    if not has_predictions:
        pytest.skip("Sem predictions no ambiente")

    data = client.get("/api/predict/predictions/latest?symbol=EURUSD").json()
    assert isinstance(data["models"], list)
    for m in data["models"]:
        assert "model" in m


def test_invalid_symbol_returns_404(client):
    """S\u00edmbolo n\u00e3o reconhecido deve retornar 404."""
    res = client.get("/api/predict/predictions/latest?symbol=INVALID_XYZ")
    assert res.status_code in (400, 404)


def test_missing_symbol_query_returns_422(client):
    """Falta do par\u00e2metro `symbol` (Query obrigat\u00f3ria) \u2192 422."""
    res = client.get("/api/predict/predictions/latest")
    assert res.status_code == 422
