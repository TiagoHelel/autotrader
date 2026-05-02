"""
Interface base para modelos de previsao.
Todos os modelos devem implementar esta interface.
"""

from abc import ABC, abstractmethod

import numpy as np


class BasePredictor(ABC):
    """Interface base para modelos de previsao de preco."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome unico do modelo."""
        ...

    @property
    def params(self) -> dict:
        """Parametros do modelo para tracking."""
        return {}

    @property
    def features_used(self) -> list[str]:
        """Lista de features usadas pelo modelo."""
        return ["all"]

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Treina o modelo."""
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Gera previsoes.

        Args:
            X: input array (1, n_features) ou (n_samples, n_features)

        Returns:
            array (n_samples, 3) - previsoes t+1, t+2, t+3
        """
        ...

    @property
    def is_fitted(self) -> bool:
        """Retorna True se o modelo ja foi treinado."""
        return getattr(self, "_fitted", False)
