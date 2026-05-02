"""
Registro centralizado de modelos.
Gerencia instancias e treino de todos os modelos.
"""

import logging

import numpy as np

from src.models.base import BasePredictor
from src.models.naive import NaivePredictor
from src.models.linear import LinearPredictor
from src.models.random_forest import RandomForestPredictor
from src.models.xgboost_model import XGBoostPredictor
from src.models.ema_heuristic import EMAHeuristicPredictor

logger = logging.getLogger(__name__)


def create_all_models(symbol: str | None = None) -> list[BasePredictor]:
    """Cria instancias de todos os modelos disponíveis.

    If a symbol is provided and a champion exists for its group, that
    champion's params are used instead of the hardcoded defaults.
    """
    xgb_params: dict = {
        "n_estimators": 200, "max_depth": 4, "learning_rate": 0.1,
        "subsample": 0.7, "colsample_bytree": 0.7, "reg_lambda": 1.0,
        "early_stopping_rounds": 20,
    }
    rf_params: dict = {
        "n_estimators": 100, "max_depth": 8, "min_samples_leaf": 10,
    }

    if symbol:
        try:
            from src.training.hpo_store import get_best_params_for_symbol
            champion_xgb = get_best_params_for_symbol("xgboost", symbol)
            if champion_xgb:
                xgb_params = {**xgb_params, **champion_xgb}
                logger.info("%s: using champion XGBoost params %s", symbol, champion_xgb)
            champion_rf = get_best_params_for_symbol("random_forest", symbol)
            if champion_rf:
                rf_params = {**rf_params, **champion_rf}
                logger.info("%s: using champion RF params %s", symbol, champion_rf)
        except Exception:
            logger.debug("Could not load champion params for %s, using defaults", symbol)

    return [
        NaivePredictor(),
        LinearPredictor(alpha=1.0),
        RandomForestPredictor(**rf_params),
        XGBoostPredictor(**xgb_params),
        EMAHeuristicPredictor(momentum_factor=0.3),
    ]


class ModelRegistry:
    """Registro e gerenciamento de modelos por simbolo."""

    def __init__(self):
        # {symbol: [models]}
        self._models: dict[str, list[BasePredictor]] = {}

    def get_models(self, symbol: str) -> list[BasePredictor]:
        """Retorna modelos para o simbolo, criando se necessario."""
        if symbol not in self._models:
            self._models[symbol] = create_all_models(symbol=symbol)
        return self._models[symbol]

    def invalidate(self, symbol: str) -> None:
        """Remove o cache do simbolo, forcando recriacao com params atualizados na proxima chamada."""
        self._models.pop(symbol, None)

    def train_all(self, symbol: str, X: np.ndarray, y: np.ndarray) -> dict[str, bool]:
        """Treina todos os modelos para um simbolo."""
        models = self.get_models(symbol)
        results = {}

        for model in models:
            try:
                model.fit(X, y)
                results[model.name] = True
                logger.info(f"{symbol} | {model.name}: treinado com {len(X)} amostras")
            except Exception as e:
                results[model.name] = False
                logger.error(f"{symbol} | {model.name}: erro no treino - {e}")

        return results

    def predict_all(self, symbol: str, X: np.ndarray) -> dict[str, np.ndarray]:
        """Roda previsao em todos os modelos treinados."""
        models = self.get_models(symbol)
        predictions = {}

        for model in models:
            if not model.is_fitted:
                logger.warning(f"{symbol} | {model.name}: nao treinado, pulando")
                continue
            try:
                pred = model.predict(X)
                predictions[model.name] = pred
            except Exception as e:
                logger.error(f"{symbol} | {model.name}: erro na previsao - {e}")

        return predictions

    @property
    def all_model_names(self) -> list[str]:
        """Lista nomes de todos os modelos."""
        return [m.name for m in create_all_models(symbol=None)]

    def get_model_info(self, symbol: str) -> list[dict]:
        """Retorna info de todos os modelos para um simbolo."""
        models = self.get_models(symbol)
        return [
            {
                "name": m.name,
                "params": m.params,
                "features_used": m.features_used,
                "is_fitted": m.is_fitted,
            }
            for m in models
        ]
