"""
Engine de previsao.
Orquestra coleta, features, modelos e avaliacao para cada ciclo.
Integra regime de mercado, noticias e LLM sentiment.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from src.mt5.connection import MT5Connection
from src.data.collector import collect_update, load_raw
from src.features.engineering import (
    compute_features,
    prepare_dataset,
    prepare_inference_input,
    save_features,
)
from src.features.regime import get_current_regime
from src.features.session import add_session_features, get_current_session_info
from src.features.news_features import (
    normalize_news,
    build_news_features,
    get_news_feature_columns,
)
from src.data.news.investing import load_news_raw
from src.llm.news_sentiment import load_llm_features
from src.models.registry import ModelRegistry
from src.evaluation.evaluator import evaluate_predictions
from src.evaluation.tracker import log_experiment
from src.evaluation.cpcv import run_cpcv
from src.evaluation.overfitting import overfitting_score, save_validation_results
from src.evaluation.feature_importance import save_feature_importance
from src.decision.signal import generate_signals_for_models, generate_ensemble_signal, log_signal
from src.utils.logging import log_prediction, log_decision, log_session_metrics

logger = logging.getLogger(__name__)


def _sanitize_prediction_array(pred: np.ndarray, current_price: float, model_name: str) -> np.ndarray:
    """Garante que previsoes salvas sejam precos plausiveis."""
    pred = np.array(pred, dtype=float, copy=True)
    if pred.ndim == 1:
        pred = pred.reshape(1, -1)

    invalid_mask = (
        ~np.isfinite(pred)
        | (pred <= 0)
        | (pred < current_price * 0.2)
        | (pred > current_price * 5.0)
    )
    if invalid_mask.any():
        logger.warning(f"{model_name}: previsao invalida detectada, substituindo por current_price")
        pred[invalid_mask] = float(current_price)
    return pred


class PredictionEngine:
    """Motor principal de previsao."""

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.registry = ModelRegistry()
        self._trained = set()  # simbolos ja treinados
        self._cycle_count = 0
        self._news_df = pd.DataFrame()  # cache de noticias normalizadas
        self._llm_df = pd.DataFrame()   # cache de features LLM

    def run_cycle(self, conn: MT5Connection) -> dict:
        """
        Executa um ciclo completo de previsao.

        1. Atualiza dados
        2. Gera features
        3. Treina modelos (se necessario)
        4. Gera previsoes
        5. Avalia previsoes anteriores
        6. Salva tudo

        Returns:
            dict com resultados do ciclo
        """
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        logger.info(f"=== CICLO {self._cycle_count} INICIADO ===")

        results = {
            "cycle": self._cycle_count,
            "timestamp": cycle_start.isoformat(),
            "symbols": {},
        }

        # 1. Atualizar dados
        logger.info("Atualizando dados...")
        raw_data = collect_update(conn, self.symbols)

        # Carregar noticias e LLM features (compartilhados entre simbolos)
        self._load_news_data()

        for symbol in self.symbols:
            try:
                symbol_result = self._process_symbol(symbol, raw_data.get(symbol), conn)
                results["symbols"][symbol] = symbol_result
            except Exception as e:
                logger.error(f"{symbol}: erro no ciclo - {e}")
                results["symbols"][symbol] = {"error": str(e)}

        elapsed = (datetime.utcnow() - cycle_start).total_seconds()
        results["elapsed_seconds"] = elapsed
        logger.info(f"=== CICLO {self._cycle_count} CONCLUIDO em {elapsed:.1f}s ===")

        return results

    def _process_symbol(
        self, symbol: str, raw_df: pd.DataFrame, conn: MT5Connection
    ) -> dict:
        """Processa um simbolo: features, treino, previsao, avaliacao."""
        result = {}

        # Carrega dados raw
        if raw_df is None or raw_df.empty:
            raw_df = load_raw(symbol)
        if raw_df.empty:
            return {"error": "sem dados"}

        # 2. Gerar features (tecnicas + regime)
        featured_df = compute_features(raw_df)

        # 2b. Adicionar session features
        featured_df = add_session_features(featured_df, symbol)

        # 2c. Adicionar news features
        featured_df = self._add_news_features(featured_df, symbol)
        save_features(featured_df, symbol)

        # Log regime atual
        regime = get_current_regime(featured_df)
        result["regime"] = regime
        logger.info(
            f"{symbol}: regime={regime.get('trend_label')} "
            f"vol={regime.get('volatility_label')} "
            f"range={regime.get('range_label')}"
        )

        # 3. Treinar modelos com CPCV (na primeira vez ou a cada N ciclos)
        retrain = symbol not in self._trained or self._cycle_count % 50 == 0
        if retrain:
            X, y, _ = prepare_dataset(featured_df)
            if len(X) > 0:
                # CPCV: validacao cruzada com purge + embargo
                cpcv_results = self._run_cpcv_validation(symbol, X, y)
                result["cpcv"] = cpcv_results

                # Treinar modelo final com todos os dados
                train_results = self.registry.train_all(symbol, X, y)
                result["train"] = train_results
                self._trained.add(symbol)

                # Feature importance (XGBoost + RF)
                self._save_feature_importance(symbol, featured_df)

                # Log experimentos com metricas CPCV
                for model in self.registry.get_models(symbol):
                    if model.is_fitted:
                        model_cpcv = cpcv_results.get(model.name, {})
                        metrics = {
                            "accuracy": model_cpcv.get("mean_accuracy"),
                            "std": model_cpcv.get("std_accuracy"),
                        }
                        log_experiment(model, symbol, len(X), metrics=metrics)

        # 4. Gerar previsoes (ultimos 10 candles)
        X_infer = prepare_inference_input(featured_df)
        if X_infer.size == 0:
            return {**result, "error": "dados insuficientes para inferencia"}

        current_price = featured_df["close"].iloc[-1]
        predictions = self.registry.predict_all(symbol, X_infer)
        predictions = {
            name: _sanitize_prediction_array(pred, current_price, name)
            for name, pred in predictions.items()
        }

        # Salvar previsoes
        self._save_predictions(symbol, predictions, current_price)
        result["predictions"] = {
            name: pred[0].tolist() for name, pred in predictions.items()
        }
        result["current_price"] = float(current_price)

        # Log previsoes
        for model_name, pred in predictions.items():
            log_prediction(
                symbol, model_name,
                {"t1": pred[0][0], "t2": pred[0][1], "t3": pred[0][2]},
                current_price,
            )

        # 5. Gerar sinais de trade (com session awareness)
        session_info = get_current_session_info(symbol)
        session_score = session_info.get("session_score", None)
        result["session"] = session_info

        signals = generate_signals_for_models(
            {name: pred[0].tolist() for name, pred in predictions.items()},
            current_price,
            session_score=session_score,
        )
        result["signals"] = {
            name: {"signal": s["signal"], "confidence": s["confidence"], "expected_return": s["expected_return"]}
            for name, s in signals.items()
        }

        # Log sinais
        for model_name, sig in signals.items():
            log_signal(symbol, model_name, sig)

        # Sinal ensemble
        ensemble = generate_ensemble_signal(signals)
        result["ensemble_signal"] = ensemble
        log_signal(symbol, "ensemble", ensemble)

        # Log session metrics
        primary_session = ", ".join(session_info.get("active_sessions", []))
        log_session_metrics(
            symbol=symbol,
            session=primary_session,
            session_score=session_score or 0.0,
            signal=ensemble.get("signal", "HOLD"),
            model=result.get("regime", {}).get("trend_label", "unknown"),
            confidence=ensemble.get("confidence", 0.0),
        )

        # 6. Avaliar previsoes anteriores
        metrics = evaluate_predictions(symbol, raw_df)
        if not metrics.empty:
            result["evaluated"] = len(metrics)

        # 7. Auto-backtest (a cada 50 ciclos)
        if self._cycle_count % 50 == 0:
            self._run_auto_backtest(symbol)

        log_decision(symbol, "prediction_cycle", f"cycle={self._cycle_count}")

        return result

    def _save_predictions(
        self,
        symbol: str,
        predictions: dict[str, np.ndarray],
        current_price: float,
    ) -> None:
        """Salva previsoes em parquet."""
        pred_dir = settings.predictions_dir
        pred_dir.mkdir(parents=True, exist_ok=True)
        filepath = pred_dir / f"{symbol}.parquet"

        timestamp = datetime.utcnow().isoformat()
        rows = []

        for model_name, pred in predictions.items():
            rows.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "model": model_name,
                "current_price": current_price,
                "pred_t1": float(pred[0][0]),
                "pred_t2": float(pred[0][1]),
                "pred_t3": float(pred[0][2]),
            })

        new_df = pd.DataFrame(rows)

        if filepath.exists():
            existing = pd.read_parquet(filepath)
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df

        combined.to_parquet(filepath, index=False)

    def _load_news_data(self) -> None:
        """Carrega e normaliza noticias + LLM features."""
        try:
            raw_news = load_news_raw()
            if not raw_news.empty:
                self._news_df = normalize_news(raw_news)
            self._llm_df = load_llm_features()
        except Exception as e:
            logger.warning(f"Erro ao carregar noticias: {e}")
            self._news_df = pd.DataFrame()
            self._llm_df = pd.DataFrame()

    def _add_news_features(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Adiciona features de noticias ao DataFrame de features."""
        if self._news_df.empty or df.empty:
            # Preenche com zeros
            for col in get_news_feature_columns():
                df[col] = 0.0
            return df

        # Para cada candle, calcular features de noticias
        news_rows = []
        for _, row in df.iterrows():
            candle_time = pd.to_datetime(row.get("time"))
            if pd.isna(candle_time):
                news_rows.append({col: 0.0 for col in get_news_feature_columns()})
                continue

            features = build_news_features(
                symbol=symbol,
                current_time=candle_time.to_pydatetime(),
                news_df=self._news_df,
                llm_df=self._llm_df if not self._llm_df.empty else None,
            )
            news_rows.append(features)

        news_features_df = pd.DataFrame(news_rows, index=df.index)
        df = pd.concat([df, news_features_df], axis=1)
        return df

    def _run_cpcv_validation(self, symbol: str, X: np.ndarray, y: np.ndarray) -> dict:
        """Roda CPCV para todos os modelos e salva resultados."""
        from src.models.registry import create_all_models
        from src.models.xgboost_model import XGBoostPredictor
        from src.models.random_forest import RandomForestPredictor
        from src.models.linear import LinearPredictor

        # Mapeamento modelo -> (classe, kwargs) para CPCV
        model_configs = {
            "xgboost": (XGBoostPredictor, {
                "n_estimators": 200, "max_depth": 4, "learning_rate": 0.1,
            }),
            "random_forest": (RandomForestPredictor, {
                "n_estimators": 100, "max_depth": 8,
            }),
            "linear": (LinearPredictor, {"alpha": 1.0}),
        }

        all_results = {}
        for model_name, (model_cls, model_kwargs) in model_configs.items():
            try:
                cpcv_result = run_cpcv(
                    model_class=model_cls,
                    model_kwargs=model_kwargs,
                    X=X, y=y,
                    n_splits=5,
                    embargo_pct=0.02,
                )
                all_results[model_name] = cpcv_result

                # Overfitting detection
                for detail in cpcv_result.get("fold_details", []):
                    gap = detail.get("overfit_gap", 0)
                    overfitting_score(detail["train_score"], detail["val_score"])

            except Exception as e:
                logger.warning(f"{symbol} | {model_name}: CPCV failed - {e}")
                all_results[model_name] = {"mean_accuracy": None, "std_accuracy": None}

        # Salvar resultados de validacao
        try:
            save_validation_results(symbol, all_results)
        except Exception as e:
            logger.warning(f"{symbol}: erro ao salvar validacao - {e}")

        return all_results

    def _save_feature_importance(self, symbol: str, featured_df: pd.DataFrame) -> None:
        """Salva feature importance para XGBoost e RF."""
        try:
            models = self.registry.get_models(symbol)
            for model in models:
                if model.is_fitted and model.name in ("xgboost", "random_forest"):
                    save_feature_importance(model, symbol, featured_df)
        except Exception as e:
            logger.warning(f"{symbol}: erro ao salvar feature importance - {e}")

    def _run_auto_backtest(self, symbol: str) -> None:
        """Roda backtest automatico para um simbolo."""
        try:
            from src.backtest.engine import run_backtest_by_model
            results = run_backtest_by_model(symbol)
            if results:
                logger.info(f"{symbol}: auto-backtest concluido para {len(results)} modelos")
                for model_name, res in results.items():
                    pnl = res.get("metrics", {}).get("pnl_total", 0)
                    log_decision(symbol, f"backtest_{model_name}", f"pnl={pnl:.2f}")
        except Exception as e:
            logger.error(f"{symbol}: erro no auto-backtest - {e}")

    def initial_setup(self, conn: MT5Connection) -> None:
        """Setup inicial: coleta dados e treina modelos."""
        from src.data.collector import collect_initial

        logger.info("Setup inicial: coletando dados...")
        raw_data = collect_initial(conn, self.symbols)
        self._load_news_data()

        for symbol, raw_df in raw_data.items():
            logger.info(f"Treinando modelos para {symbol}...")
            featured_df = compute_features(raw_df)
            featured_df = add_session_features(featured_df, symbol)
            featured_df = self._add_news_features(featured_df, symbol)
            save_features(featured_df, symbol)

            X, y, _ = prepare_dataset(featured_df)
            if len(X) > 0:
                # CPCV validation
                cpcv_results = self._run_cpcv_validation(symbol, X, y)

                # Treinar modelo final com todos os dados
                self.registry.train_all(symbol, X, y)
                self._trained.add(symbol)

                # Feature importance
                self._save_feature_importance(symbol, featured_df)

                for model in self.registry.get_models(symbol):
                    if model.is_fitted:
                        model_cpcv = cpcv_results.get(model.name, {})
                        metrics = {
                            "accuracy": model_cpcv.get("mean_accuracy"),
                            "std": model_cpcv.get("std_accuracy"),
                        }
                        log_experiment(model, symbol, len(X), metrics=metrics)

        logger.info(f"Setup inicial concluido: {len(self._trained)} simbolos treinados")
