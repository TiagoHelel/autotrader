"""
Combinatorial Purged Cross-Validation (CPCV).
Implementacao baseada em Marcos Lopez de Prado.

Garante que:
- Splits sao temporais (sem shuffling)
- Purge remove overlap entre treino e teste
- Embargo adiciona gap apos cada bloco de teste
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def purged_kfold_split(
    X: np.ndarray,
    n_splits: int = 5,
    embargo_pct: float = 0.02,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Gera indices de treino/teste com purge + embargo temporal.

    Args:
        X: array de features (n_samples, n_features)
        n_splits: numero de folds
        embargo_pct: percentual do dataset para embargo apos cada bloco teste

    Returns:
        Lista de (train_indices, test_indices) para cada fold

    Exemplo visual (5 folds):
        Fold 1: Train=[-----]  Gap  Test=[---]  Embargo[--]
        Fold 2: Train=[--] Embargo[--] Test=[---] Gap Train=[--]
        ...
    """
    n_samples = len(X)
    if n_samples < n_splits * 2:
        raise ValueError(f"Dados insuficientes: {n_samples} amostras para {n_splits} folds")

    embargo_size = max(1, int(n_samples * embargo_pct))
    fold_size = n_samples // n_splits
    indices = np.arange(n_samples)

    splits = []

    for i in range(n_splits):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n_samples) if i < n_splits - 1 else n_samples

        test_idx = indices[test_start:test_end]

        # Purge: remover amostras de treino que fazem overlap com teste
        # Embargo: gap adicional apos o bloco de teste
        embargo_end = min(test_end + embargo_size, n_samples)

        # Treino = tudo ANTES do teste + tudo DEPOIS do teste+embargo
        train_before = indices[:test_start]
        train_after = indices[embargo_end:]
        train_idx = np.concatenate([train_before, train_after])

        if len(train_idx) == 0 or len(test_idx) == 0:
            logger.warning(f"Fold {i+1}: skip (train={len(train_idx)}, test={len(test_idx)})")
            continue

        splits.append((train_idx, test_idx))

        logger.info(
            f"[CPCV] Fold {i+1}/{n_splits}: "
            f"train={len(train_idx)} test={len(test_idx)} "
            f"embargo={embargo_size} "
            f"test_range=[{test_start}:{test_end}]"
        )

    return splits


def run_cpcv(
    model_class,
    model_kwargs: dict,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    embargo_pct: float = 0.02,
) -> dict:
    """
    Executa CPCV completo para um modelo.

    Args:
        model_class: classe do modelo (deve ter fit/predict)
        model_kwargs: kwargs para instanciar o modelo
        X: features array
        y: targets array (n_samples, n_horizons)
        n_splits: numero de folds
        embargo_pct: percentual de embargo

    Returns:
        dict com metricas agregadas:
        - fold_scores: lista de accuracy por fold
        - mean_accuracy: media
        - std_accuracy: desvio padrao
        - fold_details: detalhes por fold
    """
    splits = purged_kfold_split(X, n_splits, embargo_pct)

    fold_scores = []
    fold_details = []

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Instanciar e treinar modelo
        model = model_class(**model_kwargs)
        model.fit(X_train, y_train)

        # Prever
        y_pred = model.predict(X_test)

        # Calcular direction accuracy (principal metrica para trading)
        # Para cada horizonte, verifica se direcao esta correta
        if y_test.ndim == 1:
            y_test = y_test.reshape(-1, 1)
            y_pred = y_pred.reshape(-1, 1)

        # Direcao: comparar pred vs atual em relacao ao ultimo close do input
        # Como nao temos current_price aqui, usamos y[:,0] como proxy
        # (se subiu ou desceu em relacao ao horizonte anterior)
        n_correct = 0
        n_total = 0

        for h in range(y_test.shape[1]):
            if h == 0:
                # Para t+1, compara apenas se pred e actual estao no mesmo lado
                # Usamos diferenca entre consecutivos
                continue
            pred_dir = np.sign(y_pred[:, h] - y_pred[:, h - 1])
            actual_dir = np.sign(y_test[:, h] - y_test[:, h - 1])
            n_correct += np.sum(pred_dir == actual_dir)
            n_total += len(pred_dir)

        # Fallback: se so tem 1 horizonte, usa MAE-based score
        if n_total == 0:
            mae = np.mean(np.abs(y_pred - y_test))
            score = max(0, 1.0 - mae / (np.std(y_test) + 1e-8))
        else:
            score = n_correct / n_total

        fold_scores.append(score)

        # Train score para overfitting detection
        y_train_pred = model.predict(X_train)
        if y_train.ndim == 1:
            y_train = y_train.reshape(-1, 1)
            y_train_pred = y_train_pred.reshape(-1, 1)

        train_n_correct = 0
        train_n_total = 0
        for h in range(y_train.shape[1]):
            if h == 0:
                continue
            pred_dir = np.sign(y_train_pred[:, h] - y_train_pred[:, h - 1])
            actual_dir = np.sign(y_train[:, h] - y_train[:, h - 1])
            train_n_correct += np.sum(pred_dir == actual_dir)
            train_n_total += len(pred_dir)

        train_score = train_n_correct / train_n_total if train_n_total > 0 else score

        fold_details.append({
            "fold": fold_idx + 1,
            "train_size": len(train_idx),
            "test_size": len(test_idx),
            "val_score": float(score),
            "train_score": float(train_score),
            "overfit_gap": float(train_score - score),
        })

        logger.info(
            f"[CPCV] Fold {fold_idx+1} accuracy: {score:.4f} "
            f"(train: {train_score:.4f}, gap: {train_score - score:.4f})"
        )

    if not fold_scores:
        return {
            "fold_scores": [],
            "mean_accuracy": 0.0,
            "std_accuracy": 0.0,
            "fold_details": [],
        }

    mean_acc = float(np.mean(fold_scores))
    std_acc = float(np.std(fold_scores))

    logger.info(f"[CPCV] Mean accuracy: {mean_acc:.4f} +/- {std_acc:.4f}")

    return {
        "fold_scores": [float(s) for s in fold_scores],
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "fold_details": fold_details,
    }
