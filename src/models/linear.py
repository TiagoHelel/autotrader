"""
Modelo de regressao linear multivariada.
Um regressor por horizonte (t+1, t+2, t+3).
"""

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.models.base import BasePredictor


class LinearPredictor(BasePredictor):

    def __init__(self, alpha: float = 1.0):
        self._alpha = alpha
        self._models = [Ridge(alpha=alpha) for _ in range(3)]
        self._scaler = StandardScaler()
        self._fitted = False

    @property
    def name(self) -> str:
        return "linear_regression"

    @property
    def params(self) -> dict:
        return {"alpha": self._alpha, "type": "Ridge"}

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        X_scaled = self._scaler.fit_transform(X)
        for i, model in enumerate(self._models):
            model.fit(X_scaled, y[:, i])
        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if X.ndim == 1:
            X = X.reshape(1, -1)
        X_scaled = self._scaler.transform(X)
        preds = np.column_stack([m.predict(X_scaled) for m in self._models])
        return preds
