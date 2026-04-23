"""
Tests for src/features/engineering.py — covers branches not hit by broader flows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.features.engineering import (
    compute_features,
    load_features,
    prepare_dataset,
    prepare_inference_input,
    save_features,
)


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    (tmp_path / "data" / "features").mkdir(parents=True)
    return tmp_path


def _raw_df(n: int = 60, with_spread: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 1.10 + rng.normal(0, 0.001, n).cumsum()
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
        "open": close,
        "high": close + 0.0005,
        "low": close - 0.0005,
        "close": close,
        "tick_volume": rng.integers(100, 500, n),
    })
    if with_spread:
        df["spread"] = rng.integers(1, 5, n)
    return df


class TestComputeFeatures:
    def test_no_spread_column_fills_zero(self):
        df = _raw_df(30)
        result = compute_features(df)
        assert "spread_feature" in result.columns
        assert (result["spread_feature"] == 0.0).all()

    def test_with_spread_column(self):
        df = _raw_df(30, with_spread=True)
        result = compute_features(df)
        assert (result["spread_feature"] >= 0).all()

    def test_non_datetime_time_coerced(self):
        df = _raw_df(30)
        df["time"] = df["time"].astype(str)  # force string type
        result = compute_features(df)
        assert pd.api.types.is_datetime64_any_dtype(result["time"])
        assert "hour_sin" in result.columns


class TestPrepareDataset:
    def test_insufficient_data_returns_empty(self):
        df = _raw_df(3)
        df = compute_features(df)
        X, y, times = prepare_dataset(df, input_window=10, output_horizon=3)
        assert X.size == 0
        assert y.size == 0
        assert len(times) == 0

    def test_valid_returns_shapes(self):
        df = _raw_df(100)
        df = compute_features(df)
        X, y, times = prepare_dataset(df, input_window=5, output_horizon=3)
        assert X.ndim == 2
        assert y.ndim == 2
        assert y.shape[1] == 3
        assert len(times) == X.shape[0]

    def test_fallback_when_no_all_feature_cols(self):
        """If df has only raw OHLC, fallback still returns dataset."""
        df = _raw_df(60)
        # strip all engineered columns, keep only bare minimum
        df_bare = df[["time", "open", "high", "low", "close", "tick_volume"]].copy()
        X, y, times = prepare_dataset(df_bare, input_window=5, output_horizon=3)
        # Should not crash; may be empty or populated depending on fallback path
        assert isinstance(X, np.ndarray)


class TestPrepareInferenceInput:
    def test_insufficient_returns_empty(self):
        df = _raw_df(3)
        df = compute_features(df)
        X = prepare_inference_input(df, input_window=50)
        assert X.size == 0

    def test_valid(self):
        df = _raw_df(60)
        df = compute_features(df)
        X = prepare_inference_input(df, input_window=5)
        assert X.ndim == 2
        assert X.shape[0] == 1

    def test_fallback_feature_cols(self):
        df = _raw_df(30)
        df_bare = df[["time", "open", "high", "low", "close", "tick_volume"]].copy()
        X = prepare_inference_input(df_bare, input_window=5)
        assert isinstance(X, np.ndarray)


class TestSaveLoadFeatures:
    def test_save_and_load_roundtrip(self, tmp_project):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
        save_features(df, "EURUSD")
        assert (settings.features_dir / "EURUSD.parquet").exists()
        loaded = load_features("EURUSD")
        assert len(loaded) == 3

    def test_load_missing_returns_empty(self, tmp_project):
        result = load_features("NONEXISTENT")
        assert result.empty
