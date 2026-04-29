"""
Tests for src/decision/conviction.py — temporal conviction computation.

Conviction is "high" when the last 3 prediction vintages all agree on the
direction of the upcoming candle (T+1 target):
  - T-2 vintage: pred_t3 direction
  - T-1 vintage: pred_t2 direction
  - T   vintage: pred_t1 direction
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.decision.conviction import (
    compute_temporal_conviction,
    compute_all_convictions,
    _direction,
)


# -------------------- helpers --------------------

def _make_parquet(tmp_path, symbol: str, rows: list[dict]) -> None:
    """Write a minimal predictions parquet for the given symbol."""
    df = pd.DataFrame(rows)
    (tmp_path / f"{symbol}.parquet").parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp_path / f"{symbol}.parquet", index=False)


def _row(model: str, current_price: float, t1: float, t2: float, t3: float) -> dict:
    return {
        "model": model,
        "current_price": current_price,
        "pred_t1": t1,
        "pred_t2": t2,
        "pred_t3": t3,
    }


# -------------------- _direction --------------------

class TestDirection:
    def test_up(self):
        assert _direction(1.1010, 1.1000) == 1

    def test_down(self):
        assert _direction(1.0990, 1.1000) == -1

    def test_flat(self):
        assert _direction(1.1000, 1.1000) == 0


# -------------------- compute_temporal_conviction --------------------

class TestComputeTemporalConviction:
    def test_unknown_when_no_file(self, tmp_path):
        result = compute_temporal_conviction("EURUSD", "xgboost", tmp_path)
        assert result == "unknown"

    def test_unknown_when_fewer_than_3_rows(self, tmp_path):
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("xgboost", 1.1001, 1.1006, 1.1011, 1.1016),
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "unknown"

    def test_high_when_all_three_vintages_agree_up(self, tmp_path):
        # T-2: pred_t3 > current → direction up
        # T-1: pred_t2 > current → direction up
        # T  : pred_t1 > current → direction up
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T-2 (t3 used)
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T-1 (t2 used)
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T   (t1 used)
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "high"

    def test_high_when_all_three_vintages_agree_down(self, tmp_path):
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.0995, 1.0990, 1.0985),
            _row("xgboost", 1.1000, 1.0995, 1.0990, 1.0985),
            _row("xgboost", 1.1000, 1.0995, 1.0990, 1.0985),
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "high"

    def test_low_when_vintages_disagree(self, tmp_path):
        # T-2's pred_t3 points up, but T's pred_t1 points down
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T-2: t3 → up
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.0985),  # T-1: t2 → up
            _row("xgboost", 1.1000, 1.0990, 1.0985, 1.0980),  # T  : t1 → down
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "low"

    def test_low_when_one_vintage_is_flat(self, tmp_path):
        # flat direction = 0, which breaks the "all agree and nonzero" check
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1000),  # T-2: t3 = current → flat
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T-1: t2 → up
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # T  : t1 → up
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "low"

    def test_only_uses_rows_for_the_requested_model(self, tmp_path):
        # rf has only 2 rows (not enough), xgboost has 3
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("rf", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "high"
        assert compute_temporal_conviction("EURUSD", "rf", tmp_path) == "unknown"

    def test_uses_last_3_rows_when_more_than_3_exist(self, tmp_path):
        # First 2 rows point down (should be ignored), last 3 point up
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.0990, 1.0985, 1.0980),  # old: down
            _row("xgboost", 1.1000, 1.0990, 1.0985, 1.0980),  # old: down
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # recent: up
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # recent: up
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),  # recent: up
        ])
        assert compute_temporal_conviction("EURUSD", "xgboost", tmp_path) == "high"


# -------------------- compute_all_convictions --------------------

class TestComputeAllConvictions:
    def test_returns_dict_for_all_models(self, tmp_path):
        _make_parquet(tmp_path, "EURUSD", [
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
            _row("xgboost", 1.1000, 1.1005, 1.1010, 1.1015),
        ])
        result = compute_all_convictions("EURUSD", ["xgboost", "rf"], tmp_path)
        assert set(result.keys()) == {"xgboost", "rf"}
        assert result["xgboost"] == "high"
        assert result["rf"] == "unknown"

    def test_empty_model_list_returns_empty_dict(self, tmp_path):
        result = compute_all_convictions("EURUSD", [], tmp_path)
        assert result == {}
