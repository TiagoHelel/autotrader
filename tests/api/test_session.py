"""Testes dos endpoints de session (/api/session/*)."""



def test_session_current(client):
    """Session atual retorna `session_score` no payload."""
    res = client.get("/api/session/current?symbol=EURUSD")
    assert res.status_code == 200

    data = res.json()
    assert "session_score" in data


def test_session_score_range(client):
    """session_score deve estar em [0, 1]."""
    data = client.get("/api/session/current?symbol=EURUSD").json()
    score = data["session_score"]
    assert score is not None
    assert 0.0 <= float(score) <= 1.0


def test_session_has_regime(client):
    """Payload inclui info de regime (dict, pode ser vazio se sem features)."""
    data = client.get("/api/session/current?symbol=EURUSD").json()
    assert "regime" in data
    assert isinstance(data["regime"], dict)


def test_session_weights(client):
    """`/api/session/weights` retorna dict com 'weights'."""
    res = client.get("/api/session/weights")
    assert res.status_code == 200

    data = res.json()
    assert "weights" in data
    assert isinstance(data["weights"], dict)
