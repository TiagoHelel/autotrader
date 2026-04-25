"""
Property-based tests for the backtest metrics pipeline.

Target: src.backtest.engine._compute_metrics
Why: financial metrics are the final gate for "is this strategy profitable?"
Any miscomputation → bad go/no-go decisions for real-money trading.

Invariants:
  1. winrate in [0, 100]
  2. max_drawdown <= 0 (drawdown is never positive)
  3. pnl_total == sum(pnl_pips)
  4. total_trades == winning + losing
  5. All-winning trades → profit_factor = inf (gross_loss = 0)
  6. All-losing trades → profit_factor = 0 (gross_profit = 0)
  7. Reversing trade order → same pnl_total, winrate, profit_factor (order-invariants)
"""
from __future__ import annotations

import pandas as pd
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.backtest.engine import _compute_metrics


@st.composite
def trades_df_strat(draw):
    n = draw(st.integers(min_value=1, max_value=50))
    pnl_pips = draw(st.lists(
        st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=n, max_size=n,
    ))
    entry_prices = draw(st.lists(
        st.floats(min_value=0.8, max_value=200, allow_nan=False, allow_infinity=False),
        min_size=n, max_size=n,
    ))
    pnl_price = draw(st.lists(
        st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        min_size=n, max_size=n,
    ))
    return pd.DataFrame({
        "pnl_pips": pnl_pips,
        "pnl_price": pnl_price,
        "entry_price": entry_prices,
    })


@given(trades_df_strat())
@settings(max_examples=200, deadline=None)
def test_winrate_bounded(df):
    m = _compute_metrics(df)
    assert 0.0 <= m["winrate"] <= 100.0


@given(trades_df_strat())
@settings(max_examples=200, deadline=None)
def test_drawdown_non_positive(df):
    m = _compute_metrics(df)
    assert m["max_drawdown"] <= 1e-9  # tolerate rounding


@given(trades_df_strat())
@settings(max_examples=200, deadline=None)
def test_pnl_total_matches_sum(df):
    m = _compute_metrics(df)
    # rounded to 2dp in implementation
    assert abs(m["pnl_total"] - round(float(df["pnl_pips"].sum()), 2)) < 0.02


@given(trades_df_strat())
@settings(max_examples=200, deadline=None)
def test_trade_counts_consistent(df):
    m = _compute_metrics(df)
    assert m["total_trades"] == m["winning_trades"] + m["losing_trades"]


@given(
    st.lists(st.floats(min_value=0.1, max_value=50, allow_nan=False),
             min_size=1, max_size=20),
)
@settings(max_examples=100, deadline=None)
def test_all_winners_profit_factor_is_infinite(pnls):
    df = pd.DataFrame({
        "pnl_pips": pnls,
        "pnl_price": [p / 100 for p in pnls],
        "entry_price": [1.1] * len(pnls),
    })
    m = _compute_metrics(df)
    assert m["profit_factor"] == float("inf")
    assert m["winrate"] == 100.0


@given(
    st.lists(st.floats(min_value=-50, max_value=-0.1, allow_nan=False),
             min_size=1, max_size=20),
)
@settings(max_examples=100, deadline=None)
def test_all_losers_profit_factor_zero(pnls):
    df = pd.DataFrame({
        "pnl_pips": pnls,
        "pnl_price": [p / 100 for p in pnls],
        "entry_price": [1.1] * len(pnls),
    })
    m = _compute_metrics(df)
    assert m["profit_factor"] == 0
    assert m["winrate"] == 0.0


@given(trades_df_strat())
@settings(max_examples=100, deadline=None)
def test_reversed_order_preserves_order_invariants(df):
    assume(len(df) >= 2)
    m1 = _compute_metrics(df)
    m2 = _compute_metrics(df.iloc[::-1].reset_index(drop=True))
    # These metrics should be order-invariant
    assert m1["pnl_total"] == m2["pnl_total"]
    assert m1["winrate"] == m2["winrate"]
    assert m1["total_trades"] == m2["total_trades"]
    assert m1["winning_trades"] == m2["winning_trades"]
    # Max drawdown IS order-dependent → not tested here
