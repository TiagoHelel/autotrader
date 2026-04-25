"""
Tests for src/features/session.py — session detection, vectorized add, current info.
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from src.features.session import (
    SESSION_FEATURE_COLUMNS,
    SESSION_WEIGHTS,
    _compute_score,
    _compute_strength,
    _get_active_sessions,
    _get_overlaps,
    _is_session_active,
    add_session_features,
    compute_session_features,
    get_current_session_info,
)


# =============================== helpers ===============================

class TestIsSessionActive:
    def test_normal_range_inside(self):
        assert _is_session_active(10, 8, 17) is True

    def test_normal_range_outside(self):
        assert _is_session_active(7, 8, 17) is False
        assert _is_session_active(17, 8, 17) is False  # end exclusive

    def test_cross_midnight_before_midnight(self):
        assert _is_session_active(23, 22, 7) is True

    def test_cross_midnight_after_midnight(self):
        assert _is_session_active(3, 22, 7) is True

    def test_cross_midnight_outside(self):
        assert _is_session_active(12, 22, 7) is False


class TestActiveSessions:
    def test_london_hours(self):
        s = _get_active_sessions(10)
        assert s["london"] == 1
        assert s["tokyo"] == 0 or s["tokyo"] == 1  # could overlap

    def test_sydney_at_midnight(self):
        s = _get_active_sessions(2)
        assert s["sydney"] == 1


class TestOverlaps:
    def test_london_ny_overlap(self):
        o = _get_overlaps(14)
        assert o["overlap_london_ny"] == 1

    def test_tokyo_london_overlap(self):
        o = _get_overlaps(8)
        assert o["overlap_tokyo_london"] == 1

    def test_no_overlap(self):
        o = _get_overlaps(2)
        assert o["overlap_london_ny"] == 0
        assert o["overlap_tokyo_london"] == 0


class TestStrength:
    def test_count_capped_at_3(self):
        assert _compute_strength({"a": 1, "b": 1, "c": 1, "d": 1}) == 3

    def test_zero(self):
        assert _compute_strength({"a": 0, "b": 0}) == 0


class TestScore:
    def test_eurusd_london(self):
        active = {"sydney": 0, "tokyo": 0, "london": 1, "new_york": 0}
        score = _compute_score(active, "EURUSD")
        assert 0 < score <= 1

    def test_unknown_symbol_uses_default(self):
        active = {"sydney": 0, "tokyo": 0, "london": 1, "new_york": 0}
        score = _compute_score(active, "UNKNOWN")
        assert 0 < score <= 1

    def test_zero_max_score_returns_zero(self):
        """If weights sum to 0 (pathological), return 0.0."""
        with patch.dict(SESSION_WEIGHTS, {"FAKE": {"sydney": 0, "tokyo": 0, "london": 0, "new_york": 0}}):
            active = {"sydney": 1, "tokyo": 1, "london": 1, "new_york": 1}
            assert _compute_score(active, "FAKE") == 0.0


# =============================== compute_session_features ===============================

class TestComputeSessionFeatures:
    def test_nat_timestamp_returns_zeros(self):
        result = compute_session_features(pd.NaT, "EURUSD")
        for col in SESSION_FEATURE_COLUMNS:
            assert result[col] == 0.0

    def test_london_ny_overlap_hour(self):
        ts = pd.Timestamp("2025-01-01 14:00")
        r = compute_session_features(ts, "EURUSD")
        assert r["session_london"] == 1
        assert r["session_new_york"] == 1
        assert r["session_overlap_london_ny"] == 1
        assert r["session_strength"] >= 2
        assert r["session_score"] > 0

    def test_no_symbol_score_zero(self):
        ts = pd.Timestamp("2025-01-01 14:00")
        r = compute_session_features(ts, None)
        assert r["session_score"] == 0.0


# =============================== add_session_features ===============================

class TestAddSessionFeaturesVectorized:
    def test_empty_df_fills_columns(self):
        df = pd.DataFrame()
        result = add_session_features(df, "EURUSD")
        for col in SESSION_FEATURE_COLUMNS:
            assert col in result.columns

    def test_no_time_column_fills_columns(self):
        df = pd.DataFrame({"close": [1.1]})
        result = add_session_features(df, "EURUSD")
        for col in SESSION_FEATURE_COLUMNS:
            assert col in result.columns
            assert result[col].iloc[0] == 0.0

    def test_with_data(self):
        times = pd.date_range("2025-01-01 00:00", periods=24, freq="h")
        df = pd.DataFrame({"time": times, "close": np.linspace(1.1, 1.2, 24)})
        result = add_session_features(df, "EURUSD")
        assert "session_london" in result.columns
        # London 8-17 → hour 10 active
        assert result.loc[result["time"].dt.hour == 10, "session_london"].iloc[0] == 1
        # hour 2 → sydney active
        assert result.loc[result["time"].dt.hour == 2, "session_sydney"].iloc[0] == 1
        # strength capped at 3
        assert (result["session_strength"] <= 3).all()
        # score 0..1
        assert result["session_score"].min() >= 0
        assert result["session_score"].max() <= 1

    def test_unknown_symbol_uses_default_weights(self):
        times = pd.date_range("2025-01-01 08:00", periods=4, freq="h")
        df = pd.DataFrame({"time": times, "close": [1, 2, 3, 4]})
        result = add_session_features(df, "UNKNOWN_XYZ")
        assert "session_score" in result.columns

    def test_no_symbol(self):
        times = pd.date_range("2025-01-01 08:00", periods=2, freq="h")
        df = pd.DataFrame({"time": times})
        result = add_session_features(df, None)
        assert "session_score" in result.columns

    def test_zero_weights_fallback(self):
        """max_score <= 0 → session_score is 0.0."""
        times = pd.date_range("2025-01-01 08:00", periods=2, freq="h")
        df = pd.DataFrame({"time": times})
        with patch.dict(
            SESSION_WEIGHTS,
            {"ZERO": {"sydney": 0, "tokyo": 0, "london": 0, "new_york": 0}},
        ):
            result = add_session_features(df, "ZERO")
        assert (result["session_score"] == 0.0).all()


# =============================== get_current_session_info ===============================

class TestGetCurrentSessionInfo:
    def test_returns_all_fields(self):
        info = get_current_session_info("EURUSD")
        assert "timestamp_utc" in info
        assert "hour_utc" in info
        assert isinstance(info["active_sessions"], list)
        assert isinstance(info["active_overlaps"], list)
        assert "session_strength" in info
        assert "session_score" in info
        assert info["symbol"] == "EURUSD"
        assert "weights" in info

    def test_active_sessions_populated_at_london_ny_overlap(self, monkeypatch):
        """Force a known timestamp to hit the overlaps branch."""
        import datetime as real_datetime_module

        fake_now = real_datetime_module.datetime(
            2025, 1, 1, 14, 0, tzinfo=real_datetime_module.timezone.utc,
        )

        class FakeDatetime(real_datetime_module.datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        monkeypatch.setattr(real_datetime_module, "datetime", FakeDatetime)
        info = get_current_session_info("EURUSD")
        assert "london" in info["active_sessions"]
        assert "new_york" in info["active_sessions"]
        assert "overlap_london_ny" in info["active_overlaps"]

    def test_no_symbol_uses_default_weights(self):
        info = get_current_session_info(None)
        assert info["symbol"] is None
        assert info["weights"] is not None
