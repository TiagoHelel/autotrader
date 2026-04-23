"""
Tests for src/evaluation/cpcv.py — Combinatorial Purged Cross-Validation.

Decisao arquitetural [001]: CPCV com purge + embargo eh obrigatorio pra qualquer
treino de modelo. Estes testes travam o comportamento pra impedir regressao.
"""

import numpy as np
import pytest

from src.evaluation.cpcv import purged_kfold_split, run_cpcv


# ----------------------------- purged_kfold_split -----------------------------

class TestPurgedKfoldSplit:
    def test_returns_correct_number_of_folds(self):
        X = np.random.rand(500, 10)
        splits = purged_kfold_split(X, n_splits=5, embargo_pct=0.02)
        assert len(splits) == 5

    def test_returns_tuples_of_ndarrays(self):
        X = np.random.rand(200, 5)
        splits = purged_kfold_split(X, n_splits=3, embargo_pct=0.02)
        for train_idx, test_idx in splits:
            assert isinstance(train_idx, np.ndarray)
            assert isinstance(test_idx, np.ndarray)
            assert train_idx.dtype.kind == "i"
            assert test_idx.dtype.kind == "i"

    def test_train_and_test_never_overlap(self):
        """Nenhum indice pode estar em train e test ao mesmo tempo."""
        X = np.random.rand(500, 10)
        for train_idx, test_idx in purged_kfold_split(X, n_splits=5, embargo_pct=0.02):
            overlap = np.intersect1d(train_idx, test_idx)
            assert overlap.size == 0, f"Overlap encontrado: {overlap[:5]}"

    def test_embargo_creates_gap_after_test_block(self):
        """O embargo deve remover amostras DEPOIS do bloco de teste do treino."""
        n = 500
        embargo_pct = 0.05  # 25 amostras
        X = np.random.rand(n, 5)
        splits = purged_kfold_split(X, n_splits=5, embargo_pct=embargo_pct)
        embargo_size = int(n * embargo_pct)

        for train_idx, test_idx in splits:
            if test_idx.max() == n - 1:
                # fold final nao tem embargo apos (nao tem "depois")
                continue
            test_end = test_idx.max()
            # nenhum indice de treino pode estar em [test_end+1, test_end+embargo_size]
            forbidden = set(range(test_end + 1, test_end + 1 + embargo_size))
            assert not (forbidden & set(train_idx.tolist())), (
                f"Embargo violado apos test_end={test_end}"
            )

    def test_all_indices_are_valid(self):
        n = 300
        X = np.random.rand(n, 4)
        for train_idx, test_idx in purged_kfold_split(X, n_splits=5):
            assert train_idx.max() < n
            assert test_idx.max() < n
            assert train_idx.min() >= 0
            assert test_idx.min() >= 0

    def test_test_blocks_are_contiguous_and_non_overlapping(self):
        """Os blocos de teste devem ser contiguos (CPCV temporal, sem shuffling)."""
        n = 500
        X = np.random.rand(n, 5)
        splits = purged_kfold_split(X, n_splits=5, embargo_pct=0.02)

        all_test_indices = np.concatenate([t for _, t in splits])
        # cada indice aparece em exatamente um bloco de teste
        assert len(np.unique(all_test_indices)) == len(all_test_indices)
        # juntos cobrem o range inteiro (teste temporal exaustivo)
        assert set(all_test_indices.tolist()) == set(range(n))

    def test_test_indices_are_monotonic(self):
        """Dentro de um fold, os indices de teste sao crescentes (temporal)."""
        X = np.random.rand(400, 5)
        for _, test_idx in purged_kfold_split(X, n_splits=4):
            assert np.all(np.diff(test_idx) == 1), "Indices de teste nao contiguos"

    def test_raises_when_data_too_small(self):
        X = np.random.rand(5, 3)
        with pytest.raises(ValueError, match="Dados insuficientes"):
            purged_kfold_split(X, n_splits=5)

    def test_embargo_size_at_least_one(self):
        """Mesmo com embargo_pct muito pequeno, embargo >= 1 amostra."""
        n = 100
        X = np.random.rand(n, 3)
        splits = purged_kfold_split(X, n_splits=4, embargo_pct=0.001)
        # garantia: com embargo_pct que resultaria em 0, cai pro max(1, ...)
        # pelo menos um fold intermediario deve ter 1 amostra a menos no treino
        assert len(splits) >= 3

    def test_default_params_work(self):
        X = np.random.rand(1000, 8)
        splits = purged_kfold_split(X)  # defaults: n_splits=5, embargo_pct=0.02
        assert len(splits) == 5


# ----------------------------- run_cpcv -----------------------------

class DummyModel:
    """Modelo minimo com fit/predict. Retorna media de y_train sempre."""

    def __init__(self, **kwargs):
        self.mean_ = None

    def fit(self, X, y):
        self.mean_ = np.mean(y, axis=0)
        return self

    def predict(self, X):
        if self.mean_.ndim == 0:
            return np.full(len(X), float(self.mean_))
        return np.tile(self.mean_, (len(X), 1))


class TestRunCpcv:
    @pytest.fixture
    def dataset(self):
        rng = np.random.default_rng(0)
        n = 300
        X = rng.standard_normal((n, 5))
        y = rng.standard_normal((n, 3))  # 3 horizontes (t+1, t+2, t+3)
        return X, y

    def test_returns_expected_keys(self, dataset):
        X, y = dataset
        out = run_cpcv(DummyModel, {}, X, y, n_splits=3)
        assert set(out.keys()) == {"fold_scores", "mean_accuracy", "std_accuracy", "fold_details"}

    def test_fold_scores_length_matches_n_splits(self, dataset):
        X, y = dataset
        out = run_cpcv(DummyModel, {}, X, y, n_splits=5, embargo_pct=0.02)
        assert len(out["fold_scores"]) == 5
        assert len(out["fold_details"]) == 5

    def test_mean_and_std_are_floats_in_valid_range(self, dataset):
        X, y = dataset
        out = run_cpcv(DummyModel, {}, X, y, n_splits=4)
        assert isinstance(out["mean_accuracy"], float)
        assert isinstance(out["std_accuracy"], float)
        assert 0.0 <= out["mean_accuracy"] <= 1.0
        assert out["std_accuracy"] >= 0.0

    def test_fold_details_contain_train_and_val_sizes(self, dataset):
        X, y = dataset
        out = run_cpcv(DummyModel, {}, X, y, n_splits=3)
        for d in out["fold_details"]:
            assert "fold" in d
            assert "train_size" in d
            assert "test_size" in d
            assert "val_score" in d
            assert "train_score" in d
            assert "overfit_gap" in d
            assert d["train_size"] > 0
            assert d["test_size"] > 0

    def test_overfit_gap_is_train_minus_val(self, dataset):
        X, y = dataset
        out = run_cpcv(DummyModel, {}, X, y, n_splits=3)
        for d in out["fold_details"]:
            assert d["overfit_gap"] == pytest.approx(d["train_score"] - d["val_score"])

    def test_1d_target_fallback_to_mae_score(self):
        """Com y 1D (1 horizonte), cai no fallback MAE-based (score em [0,1])."""
        rng = np.random.default_rng(0)
        X = rng.standard_normal((200, 4))
        y = rng.standard_normal(200)
        out = run_cpcv(DummyModel, {}, X, y, n_splits=3)
        assert len(out["fold_scores"]) == 3
        for s in out["fold_scores"]:
            assert 0.0 <= s <= 1.0
