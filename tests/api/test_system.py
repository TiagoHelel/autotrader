"""Testes de endpoints de sistema (status geral, logs)."""


def test_system_status(client):
    """`/api/predict/system/status` responde 200."""
    res = client.get("/api/predict/system/status")
    assert res.status_code == 200
    assert isinstance(res.json(), dict)


def test_logs_recent(client):
    """`/api/predict/logs/recent` responde 200 com estrutura consistente."""
    res = client.get("/api/predict/logs/recent")
    assert res.status_code == 200
    # Aceita lista ou dict wrapper — importante \u00e9 n\u00e3o quebrar.
    assert isinstance(res.json(), (list, dict))


def test_metrics_endpoint(client):
    """`/api/predict/metrics` responde 200."""
    res = client.get("/api/predict/metrics")
    assert res.status_code == 200
