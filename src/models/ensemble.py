"""
Utilitario de ensemble: agrega previsoes de multiplos modelos em uma unica
previsao (media simples por horizonte).

Compativel com o formato usado no registry: dict[model_name, array(n, 3)]
ou dict[model_name, list/array de 3 valores (t+1, t+2, t+3)].
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np


def _to_horizon_vector(pred) -> list[float]:
    """Converte uma previsao de modelo para vetor [t+1, t+2, t+3]."""
    arr = np.asarray(pred, dtype=float)
    if arr.ndim == 2:
        # (n_samples, 3) -> pega a ultima linha (previsao mais recente)
        arr = arr[-1]
    if arr.ndim != 1:
        arr = arr.flatten()
    return [float(v) for v in arr.tolist()]


def compute_ensemble(
    predictions: Mapping[str, Iterable[float]],
    weights: Mapping[str, float] | None = None,
    skip_non_finite: bool = True,
) -> list[float]:
    """
    Calcula ensemble (media simples ou ponderada) das previsoes.

    Args:
        predictions: dict[model_name -> previsao]. Cada previsao pode ser
            list/np.array de 3 valores ou array (n, 3).
        weights: pesos opcionais por modelo. Se None, usa media simples.
        skip_non_finite: se True, ignora valores NaN/Inf por horizonte.

    Returns:
        lista [ensemble_t1, ensemble_t2, ensemble_t3].

    Raises:
        ValueError: se predictions estiver vazio ou se todos os valores
            de um horizonte forem nao-finitos.
    """
    if not predictions:
        raise ValueError("predictions vazio: ensemble requer pelo menos 1 modelo")

    horizons: list[list[tuple[float, float]]] = [[], [], []]  # por horizonte: [(value, weight), ...]

    for name, pred in predictions.items():
        vec = _to_horizon_vector(pred)
        if len(vec) != 3:
            raise ValueError(
                f"Modelo '{name}' retornou {len(vec)} valores; esperado 3 (t+1, t+2, t+3)"
            )
        w = float(weights[name]) if weights and name in weights else 1.0
        for h, v in enumerate(vec):
            if skip_non_finite and not math.isfinite(v):
                continue
            horizons[h].append((v, w))

    result: list[float] = []
    for h, items in enumerate(horizons):
        if not items:
            raise ValueError(f"Horizonte t+{h+1}: nenhum valor finito para agregar")
        total_w = sum(w for _, w in items)
        if total_w == 0:
            raise ValueError(f"Horizonte t+{h+1}: soma de pesos = 0")
        weighted = sum(v * w for v, w in items) / total_w
        result.append(float(weighted))

    return result
