"""
Modelo heuristico baseado em EMA trend.
Usa EMA50 vs EMA200 para determinar direcao.
"""

import numpy as np

from config.settings import settings
from src.features.engineering import FEATURE_COLUMNS
from src.models.base import BasePredictor


class EMAHeuristicPredictor(BasePredictor):
    """
    Heuristica: se EMA50 > EMA200 (tendencia de alta), projeta close + ATR * fator.
    Se EMA50 < EMA200, projeta close - ATR * fator.
    """

    def __init__(self, momentum_factor: float = 0.3):
        self._momentum_factor = momentum_factor
        self._fitted = False

    @property
    def name(self) -> str:
        return "ema_heuristic"

    @property
    def params(self) -> dict:
        return {"momentum_factor": self._momentum_factor}

    @property
    def features_used(self) -> list[str]:
        return ["close", "ema_50", "ema_200", "atr_14", "ema_9", "ema_21"]

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        # Heuristica nao precisa treino
        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Extrai features do vetor flattened para aplicar heuristica.
        O layout real por candle pode crescer quando novas features sao adicionadas,
        entao os indices sao calculados dinamicamente a partir do input_window.
        """
        if X.ndim == 1:
            X = X.reshape(1, -1)

        idx_close = FEATURE_COLUMNS.index("close")
        idx_ema_9 = FEATURE_COLUMNS.index("ema_9")
        idx_ema_21 = FEATURE_COLUMNS.index("ema_21")
        idx_ema_50 = FEATURE_COLUMNS.index("ema_50")
        idx_ema_200 = FEATURE_COLUMNS.index("ema_200")
        idx_atr = FEATURE_COLUMNS.index("atr_14")
        input_window = max(settings.input_window, 1)
        results = []

        for row in X:
            n_features = max(len(row) // input_window, len(FEATURE_COLUMNS))
            # Pega features do ultimo candle
            last_candle_start = len(row) - n_features
            if last_candle_start < 0:
                last_candle_start = 0

            last_candle = row[last_candle_start:last_candle_start + n_features]

            close = last_candle[idx_close]
            ema_50 = last_candle[idx_ema_50]
            ema_200 = last_candle[idx_ema_200]
            atr = last_candle[idx_atr]
            ema_9 = last_candle[idx_ema_9]
            ema_21 = last_candle[idx_ema_21]

            # Direcao principal: EMA50 vs EMA200
            if ema_50 > ema_200:
                direction = 1.0
            else:
                direction = -1.0

            # Forca do momentum: EMA9 vs EMA21
            short_momentum = 1.0 if ema_9 > ema_21 else 0.5

            factor = self._momentum_factor * direction * short_momentum

            preds = [
                close + atr * factor * 1.0,  # t+1
                close + atr * factor * 1.5,  # t+2
                close + atr * factor * 2.0,  # t+3
            ]
            results.append(preds)

        return np.array(results)
