"""Testes de endpoints de modelos (performance, best, info)."""



def test_model_performance(client):
    """`/api/predict/models/performance` retorna dict com `ranking` (lista)."""
    res = client.get("/api/predict/models/performance")
    assert res.status_code == 200

    data = res.json()
    # Contrato atual: {"ranking": [...]}
    assert "ranking" in data
    assert isinstance(data["ranking"], list)


def test_best_model(client):
    """`/api/models/best?symbol=EURUSD` retorna dict com `model`."""
    res = client.get("/api/models/best?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert "model" in data
    # `model` pode ser None se n\u00e3o ha experimentos ranqueados
    assert data["model"] is None or isinstance(data["model"], dict)


def test_best_model_global(client):
    """Sem `symbol` tamb\u00e9m deve funcionar (global)."""
    res = client.get("/api/models/best")
    assert res.status_code == 200
    assert "model" in res.json()


def test_models_info(client):
    """`/api/predict/models/info` retorna dict com lista `models`."""
    res = client.get("/api/predict/models/info")
    assert res.status_code == 200

    data = res.json()
    assert "models" in data
    assert isinstance(data["models"], list)
    # registry deve expor pelo menos um modelo
    assert len(data["models"]) >= 1


def test_feature_importance(client):
    """`/api/predict/models/feature-importance` responde sem erro."""
    res = client.get("/api/predict/models/feature-importance")
    assert res.status_code == 200
