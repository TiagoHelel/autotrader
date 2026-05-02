"""
Modelo XGBoost para previsao de preco.
Um regressor por horizonte (t+1, t+2, t+3).
Regularizado com early stopping, subsample e colsample.
"""

import logging

import numpy as np
from xgboost import XGBRegressor

from src.models.base import BasePredictor

logger = logging.getLogger(__name__)


class XGBoostPredictor(BasePredictor):

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.1,
        subsample: float = 0.7,
        colsample_bytree: float = 0.7,
        reg_lambda: float = 1.0,
        early_stopping_rounds: int = 20,
    ):
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._learning_rate = learning_rate
        self._subsample = subsample
        self._colsample_bytree = colsample_bytree
        self._reg_lambda = reg_lambda
        self._early_stopping_rounds = early_stopping_rounds
        self._models = [
            XGBRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                subsample=subsample,
                colsample_bytree=colsample_bytree,
                reg_lambda=reg_lambda,
                early_stopping_rounds=early_stopping_rounds,
                n_jobs=-1,
                random_state=42,
                verbosity=0,
            )
            for _ in range(3)
        ]
        self._fitted = False

    @property
    def name(self) -> str:
        return "xgboost"

    @property
    def params(self) -> dict:
        return {
            "n_estimators": self._n_estimators,
            "max_depth": self._max_depth,
            "learning_rate": self._learning_rate,
            "subsample": self._subsample,
            "colsample_bytree": self._colsample_bytree,
            "reg_lambda": self._reg_lambda,
            "early_stopping_rounds": self._early_stopping_rounds,
        }

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        # Split interno para early stopping (85/15)
        val_split = max(1, int(len(X) * 0.85))
        X_train, X_val = X[:val_split], X[val_split:]
        y_train, y_val = y[:val_split], y[val_split:]

        for i, model in enumerate(self._models):
            if len(X_val) > 0:
                model.fit(
                    X_train, y_train[:, i],
                    eval_set=[(X_val, y_val[:, i])],
                    verbose=False,
                )
                best_round = model.best_iteration
                if best_round is not None:
                    logger.info(f"[XGB] Horizon t+{i+1}: early stopping at round {best_round}")
            else:
                model.fit(X_train, y_train[:, i])

        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if X.ndim == 1:
            X = X.reshape(1, -1)
        preds = np.column_stack([m.predict(X) for m in self._models])
        return preds
