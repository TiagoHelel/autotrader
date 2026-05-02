"""
Modelo baseline: ultimo valor (naive forecast).
Preve que o preco futuro sera igual ao ultimo close.
"""

import numpy as np

from config.settings import settings
from src.features.engineering import FEATURE_COLUMNS
from src.models.base import BasePredictor


class NaivePredictor(BasePredictor):

    @property
    def name(self) -> str:
        return "naive"

    @property
    def params(self) -> dict:
        return {"method": "last_value"}

    @property
    def features_used(self) -> list[str]:
        return ["close"]

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        # Naive nao precisa de treino
        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Repete o ultimo close para t+1, t+2, t+3."""
        if X.ndim == 1:
            X = X.reshape(1, -1)

        close_idx = FEATURE_COLUMNS.index("close")
        input_window = max(settings.input_window, 1)

        results = []
        for row in X:
            n_features_per_candle = max(len(row) // input_window, close_idx + 1)
            last_close_idx = ((input_window - 1) * n_features_per_candle) + close_idx
            if last_close_idx < len(row):
                last_close = row[last_close_idx]
            elif close_idx < len(row):
                last_close = row[close_idx]
            else:
                last_close = row[-1]
            results.append([last_close, last_close, last_close])

        return np.array(results)
