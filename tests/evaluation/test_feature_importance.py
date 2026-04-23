"""Tests for src/evaluation/feature_importance.py."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config.settings import settings
from src.evaluation.feature_importance import (
    save_feature_importance,
    load_feature_importance,
)
from src.features.engineering import ALL_FEATURE_COLUMNS


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    return tmp_path


@pytest.fixture
def featured_df():
    """DataFrame com todas as features conhecidas."""
    data = {col: [0.0, 0.1, 0.2] for col in ALL_FEATURE_COLUMNS}
    return pd.DataFrame(data)


def _fake_model(name, n_horizons=3, n_features=None, importances=None):
    """Cria um modelo mock com _models (um sub-modelo por horizonte)."""
    sub_models = []
    for h in range(n_horizons):
        m = SimpleNamespace()
        if importances is not None:
            m.feature_importances_ = importances
        else:
            n = n_features or 10
            m.feature_importances_ = np.ones(n) / n
        sub_models.append(m)
    return SimpleNamespace(name=name, _models=sub_models)


class TestSaveFeatureImportance:
    def test_xgboost_writes_parquet(self, fake_project, featured_df):
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        model = _fake_model("xgboost", n_horizons=3, importances=np.ones(n_total) / n_total)
        save_feature_importance(model, "EURUSD", featured_df)
        f = settings.metrics_dir / "feature_importance.parquet"
        assert f.exists()
        df = pd.read_parquet(f)
        assert (df["model"] == "xgboost").all()
        assert set(df["horizon"]) == {1, 2, 3}
        assert (df["symbol"] == "EURUSD").all()

    def test_random_forest_writes_parquet(self, fake_project, featured_df):
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        model = _fake_model("random_forest", importances=np.ones(n_total) / n_total)
        save_feature_importance(model, "EURUSD", featured_df)
        df = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        assert (df["model"] == "random_forest").all()

    def test_unknown_model_skipped(self, fake_project, featured_df):
        model = _fake_model("lstm", importances=np.ones(10))
        save_feature_importance(model, "EURUSD", featured_df)
        assert not (settings.metrics_dir / "feature_importance.parquet").exists()

    def test_model_without_importances_attr_skipped(self, fake_project, featured_df):
        model = SimpleNamespace(name="xgboost", _models=[SimpleNamespace()])  # no attr
        save_feature_importance(model, "EURUSD", featured_df)
        assert not (settings.metrics_dir / "feature_importance.parquet").exists()

    def test_aggregates_by_base_feature(self, fake_project, featured_df):
        # Uniform importance; after aggregation across time windows,
        # each base feature should sum equal parts.
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        importances = np.ones(n_total)
        model = _fake_model("xgboost", n_horizons=1, importances=importances)
        save_feature_importance(model, "EURUSD", featured_df)
        df = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        # Each base feature appears in window_size time slots, so importance sums to input_window
        for feat in ALL_FEATURE_COLUMNS:
            row = df[df["feature"] == feat]
            assert len(row) == 1
            assert row.iloc[0]["importance"] == pytest.approx(settings.input_window)

    def test_extra_importances_create_feature_i_keys(self, fake_project, featured_df):
        # More importances than feature_names — triggers `feature_{i}` fallback
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        importances = np.ones(n_total + 2)
        model = _fake_model("xgboost", n_horizons=1, importances=importances)
        save_feature_importance(model, "EURUSD", featured_df)
        df = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        assert any(f.startswith("feature_") for f in df["feature"])

    def test_appending_replaces_same_symbol_model(self, fake_project, featured_df):
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        model1 = _fake_model("xgboost", n_horizons=1, importances=np.ones(n_total))
        save_feature_importance(model1, "EURUSD", featured_df)
        df1 = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        len1 = len(df1)

        # Re-save same symbol/model — old rows replaced
        save_feature_importance(model1, "EURUSD", featured_df)
        df2 = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        assert len(df2) == len1  # replaced, not duplicated

        # Different symbol — appended
        save_feature_importance(model1, "GBPUSD", featured_df)
        df3 = pd.read_parquet(settings.metrics_dir / "feature_importance.parquet")
        assert set(df3["symbol"]) == {"EURUSD", "GBPUSD"}


class TestLoadFeatureImportance:
    def test_missing_file_empty(self, fake_project):
        assert load_feature_importance().empty

    def test_filter_by_symbol_and_model(self, fake_project, featured_df):
        n_total = settings.input_window * len(ALL_FEATURE_COLUMNS)
        model = _fake_model("xgboost", n_horizons=1, importances=np.ones(n_total))
        save_feature_importance(model, "EURUSD", featured_df)
        save_feature_importance(model, "GBPUSD", featured_df)

        all_df = load_feature_importance()
        assert set(all_df["symbol"]) == {"EURUSD", "GBPUSD"}

        eur = load_feature_importance(symbol="EURUSD")
        assert set(eur["symbol"]) == {"EURUSD"}

        xgb = load_feature_importance(model="xgboost")
        assert set(xgb["model"]) == {"xgboost"}
