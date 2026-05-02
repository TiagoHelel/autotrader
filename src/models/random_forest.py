"""
Modelo Random Forest para previsao de preco.
Um regressor por horizonte (t+1, t+2, t+3).
Regularizado com min_samples_leaf e max_depth conservador.
"""

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from src.models.base import BasePredictor


class RandomForestPredictor(BasePredictor):

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 8,
        min_samples_leaf: int = 10,
    ):
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._min_samples_leaf = min_samples_leaf
        self._models = [
            RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                n_jobs=-1,
                random_state=42,
            )
            for _ in range(3)
        ]
        self._fitted = False

    @property
    def name(self) -> str:
        return "random_forest"

    @property
    def params(self) -> dict:
        return {
            "n_estimators": self._n_estimators,
            "max_depth": self._max_depth,
            "min_samples_leaf": self._min_samples_leaf,
        }

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        for i, model in enumerate(self._models):
            model.fit(X, y[:, i])
        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if X.ndim == 1:
            X = X.reshape(1, -1)
        preds = np.column_stack([m.predict(X) for m in self._models])
        return preds
