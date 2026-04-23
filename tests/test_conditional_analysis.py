"""
Testes do modulo conditional_analysis.

Estrategia: gerar dataset sintetico com edge PLANTADO em uma condicao
especifica (ex: XAU hora=14 tem win_rate=70%; resto e coin flip).
Validar que evaluate_filter detecta a condicao correta como PROMISING
e rejeita as demais.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.research import conditional_analysis as ca


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolated_research_dir(tmp_path, monkeypatch):
    """Redireciona paths de persistencia pra tmp_path em cada teste."""
    rdir = tmp_path / "research"
    rdir.mkdir()
    monkeypatch.setattr(ca, "RESEARCH_DIR", rdir)
    monkeypatch.setattr(ca, "FILTER_LOG_PATH", rdir / "filter_log.parquet")
    monkeypatch.setattr(ca, "HOLDOUT_USAGE_PATH", rdir / "holdout_usage.parquet")
    return rdir


@pytest.fixture
def synthetic_dataset():
    """
    Dataset com 5000 predicoes distribuidas uniformemente em 24h para XAUUSD.
    Edge plantado: hour_utc == 14 tem win_rate=80%. Resto = 50%.
    Com 5000 candles M5 ≈ 17 dias, hour=14 tera ~200 amostras — N robusto.
    """
    rng = np.random.default_rng(seed=42)
    n = 5000
    rows = []
    base = pd.Timestamp("2025-01-01 00:00:00")
    for i in range(n):
        t = base + pd.Timedelta(minutes=5 * i)
        hour = t.hour

        # edge plantado
        if hour == 14:
            win_prob = 0.80
        else:
            win_prob = 0.50

        pnl = rng.normal(loc=2.0 if rng.random() < win_prob else -2.0, scale=1.0)

        rows.append({
            "symbol": "XAUUSD",
            "timestamp": t,
            "model": "xgboost",
            "hour_utc": hour,
            "hour_local_ny": (hour - 4) % 24,
            "session": "new_york" if 13 <= hour < 22 else "off_hours",
            "session_score": 0.8 if 13 <= hour < 22 else 0.1,
            "trend": 1,
            "volatility_regime": 1,
            "momentum": 0.0,
            "current_price": 2000.0,
            "pred_t1": 2001.0,
            "pred_t2": 2001.5,
            "pred_t3": 2002.0,
            "predicted_direction": 1,
            "confidence": 0.9,
            "expected_return": 0.001,
            "signal": "BUY",
            "actual_price_t1": 2001.0,
            "actual_price_t3": 2002.0,
            "actual_direction_t1": 1,
            "actual_return_t1_pips": 1.0,
            "pnl_if_traded_pips": pnl,
            "pnl_if_traded_net_pips": pnl - 0.3,  # spread
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# split_holdout
# ---------------------------------------------------------------------------
def test_split_holdout_temporal_is_ordered(synthetic_dataset):
    df_r, df_h = ca.split_holdout(synthetic_dataset, holdout_pct=0.20)
    assert len(df_r) + len(df_h) == len(synthetic_dataset)
    # holdout deve comecar APOS o fim de research (split temporal)
    assert df_r["timestamp"].max() <= df_h["timestamp"].min()
    # 80/20
    assert abs(len(df_h) / len(synthetic_dataset) - 0.20) < 0.01


def test_split_holdout_empty():
    empty = pd.DataFrame()
    r, h = ca.split_holdout(empty)
    assert r.empty and h.empty


# ---------------------------------------------------------------------------
# evaluate_filter
# ---------------------------------------------------------------------------
def test_filter_detects_planted_edge(synthetic_dataset):
    """Hour=14 deve aparecer como PROMISING/STRONG (edge plantado 75%)."""
    result = ca.evaluate_filter(
        synthetic_dataset,
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15)},
        hypothesis="edge plantado para teste",
    )
    assert result.n_trades > 30, "amostra suficiente"
    assert result.win_rate > 0.60, f"win rate deveria ser alto, foi {result.win_rate}"
    assert result.verdict in ("PROMISING", "STRONG")
    assert result.p_value_vs_coinflip < 0.05


def test_filter_rejects_no_edge_hour(synthetic_dataset):
    """Hour=3 nao tem edge — deve ser REJECTED ou WEAK."""
    result = ca.evaluate_filter(
        synthetic_dataset,
        filters={"symbol": "XAUUSD", "hour_utc": (3, 4)},
        hypothesis="controle negativo",
    )
    assert result.verdict not in ("PROMISING", "STRONG")


def test_filter_underpowered_when_n_small(synthetic_dataset):
    """Filtro muito restritivo — menos de 30 amostras → UNDERPOWERED."""
    # Combinar hora rara + alta confidence restringe muito
    tiny = synthetic_dataset.head(20).copy()
    result = ca.evaluate_filter(
        tiny,
        filters={"symbol": "XAUUSD"},
        hypothesis="teste de baixa N",
    )
    assert result.verdict == "UNDERPOWERED"
    assert not result.passes_n_min


def test_filter_rejects_when_n_zero(synthetic_dataset):
    result = ca.evaluate_filter(
        synthetic_dataset,
        filters={"symbol": "INEXISTENTE"},
        hypothesis="dataset vazio",
    )
    assert result.verdict == "REJECTED_N"
    assert result.n_trades == 0


# ---------------------------------------------------------------------------
# Persistencia + Bonferroni
# ---------------------------------------------------------------------------
def test_filter_log_is_persisted(synthetic_dataset, isolated_research_dir):
    ca.evaluate_filter(
        synthetic_dataset,
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15)},
        hypothesis="h1",
    )
    assert ca.FILTER_LOG_PATH.exists()
    df = pd.read_parquet(ca.FILTER_LOG_PATH)
    assert len(df) == 1
    assert df.iloc[0]["hypothesis"] == "h1"


def test_bonferroni_warning_after_many_tests(synthetic_dataset):
    """Apos N testes previos, o p ajustado deve ser p * (N+1)."""
    # roda 3 testes "previos"
    for h in ("h1", "h2", "h3"):
        ca.evaluate_filter(
            synthetic_dataset,
            filters={"symbol": "XAUUSD", "hour_utc": (int(h[-1]), int(h[-1]) + 1)},
            hypothesis=h,
        )
    # 4o teste deve ter bonferroni ajustado
    result = ca.evaluate_filter(
        synthetic_dataset,
        filters={"symbol": "XAUUSD", "hour_utc": (14, 15)},
        hypothesis="h4",
    )
    assert result.n_prior_tests == 3
    assert result.bonferroni_adjusted_p is not None
    # p * 4 (3 previos + este)
    expected = min(1.0, result.p_value_vs_coinflip * 4)
    assert abs(result.bonferroni_adjusted_p - expected) < 1e-9


def test_holdout_reuse_is_recorded(synthetic_dataset, caplog):
    """Validar o MESMO filter_hash no holdout duas vezes dispara warning."""
    _, df_h = ca.split_holdout(synthetic_dataset)
    filters = {"symbol": "XAUUSD", "hour_utc": (14, 15)}

    ca.evaluate_filter(df_h, filters, hypothesis="first", holdout=True)
    # segunda chamada — deveria logar warning
    import logging
    with caplog.at_level(logging.WARNING):
        ca.evaluate_filter(df_h, filters, hypothesis="reuso", holdout=True)
    assert any("ja foi validado em holdout" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _apply_filters edge cases
# ---------------------------------------------------------------------------
def test_apply_filters_session_list(synthetic_dataset):
    """session pode ser list — OR logico."""
    result = ca._apply_filters(
        synthetic_dataset, {"session": ["new_york", "off_hours"]}
    )
    assert set(result["session"].unique()) <= {"new_york", "off_hours"}
    assert len(result) == len(synthetic_dataset)


def test_apply_filters_confidence_min(synthetic_dataset):
    out = ca._apply_filters(synthetic_dataset, {"confidence_min": 0.95})
    assert len(out) == 0  # dataset tem conf=0.9 fixo


def test_hash_filters_stable_order():
    """Ordem de chaves nao deve mudar o hash."""
    a = {"symbol": "XAU", "hour_utc": [14, 15]}
    b = {"hour_utc": [14, 15], "symbol": "XAU"}
    assert ca._hash_filters(a) == ca._hash_filters(b)


# ---------------------------------------------------------------------------
# Wilson CI + binomial
# ---------------------------------------------------------------------------
def test_wilson_ci_bounds():
    lo, hi = ca._wilson_ci(50, 100)
    assert 0 <= lo < hi <= 1
    assert abs((lo + hi) / 2 - 0.50) < 0.05  # centrado em 0.5


def test_wilson_ci_extreme():
    lo, hi = ca._wilson_ci(0, 10)
    assert lo == 0.0
    assert hi < 0.35


def test_binomial_coinflip_not_significant():
    p = ca._binomial_test_two_sided(50, 100)
    assert p > 0.5


def test_binomial_strong_edge_significant():
    p = ca._binomial_test_two_sided(75, 100)
    assert p < 0.001
