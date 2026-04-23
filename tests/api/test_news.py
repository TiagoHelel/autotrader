"""Testes de endpoints de news (latest, features, by-symbol, analytics)."""

import pytest


def test_news_latest(client):
    """`/api/news/latest` responde 200 com `events` list."""
    res = client.get("/api/news/latest")
    assert res.status_code == 200

    data = res.json()
    assert "events" in data
    assert isinstance(data["events"], list)


def test_news_latest_limit(client):
    """`limit` param respeitado (or pass-through quando sem dados)."""
    res = client.get("/api/news/latest?limit=5")
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) <= 5


def test_news_features(client):
    """`/api/news/features?symbol=EURUSD` retorna `features` dict com news_sentiment_base."""
    res = client.get("/api/news/features?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert "features" in data
    assert data.get("symbol") == "EURUSD"

    feats = data["features"]
    if not feats:
        pytest.skip("Sem noticias dispon\u00edveis no ambiente")

    # chave contratual usada pelo frontend / ML pipeline
    assert "news_sentiment_base" in feats


def test_news_by_symbol(client):
    """`/api/news/by-symbol?symbol=EURUSD` responde com base/quote currency."""
    res = client.get("/api/news/by-symbol?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert "events" in data
    assert data.get("base_currency") == "EUR"
    assert data.get("quote_currency") == "USD"


def test_news_analytics(client):
    """`/api/news/analytics` responde 200."""
    res = client.get("/api/news/analytics")
    assert res.status_code == 200
    assert "analytics" in res.json()
