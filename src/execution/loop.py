"""
Loop continuo de previsao.
Sincroniza com fechamento de candles M5 e roda 24/7.
Inclui scraping diario de noticias e processamento LLM.
"""

import logging
import time
from datetime import datetime, timedelta

from config.settings import settings
from src.mt5 import get_mt5_connection
from src.data.collector import validate_symbols
from src.execution.engine import PredictionEngine
from src.data.news.investing import run_news_ingestion
from src.features.news_features import normalize_news
from src.llm.news_sentiment import process_news_with_llm, save_llm_features
from src.utils.logging import setup_logging, log_decision

logger = logging.getLogger(__name__)


def get_next_candle_time() -> datetime:
    """Calcula quando o proximo candle M5 vai fechar."""
    now = datetime.utcnow()
    # M5: candles fecham a cada 5 minutos (00, 05, 10, 15, ...)
    minutes = now.minute
    next_5 = (minutes // 5 + 1) * 5
    if next_5 >= 60:
        next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_time = now.replace(minute=next_5, second=0, microsecond=0)

    # Adiciona margem de 5 segundos para garantir que o candle fechou
    return next_time + timedelta(seconds=5)


def wait_for_next_candle() -> None:
    """Espera ate o proximo candle M5 fechar."""
    next_time = get_next_candle_time()
    now = datetime.utcnow()
    wait_seconds = (next_time - now).total_seconds()

    if wait_seconds > 0:
        logger.info(f"Aguardando proximo candle M5: {wait_seconds:.0f}s (ate {next_time})")
        time.sleep(wait_seconds)


def _run_news_pipeline() -> None:
    """Executa pipeline de noticias: scraping + normalizacao + LLM."""
    try:
        logger.info("Iniciando pipeline de noticias...")

        # 1. Scraping
        news_df = run_news_ingestion()
        if news_df.empty:
            logger.info("Nenhuma noticia coletada")
            return

        # 2. Normalizar
        normalized = normalize_news(news_df)

        # 3. Processar com LLM
        try:
            llm_df = process_news_with_llm(normalized)
            if not llm_df.empty:
                save_llm_features(llm_df)
                logger.info(f"LLM processou {len(llm_df)} noticias")
        except Exception as e:
            logger.warning(f"LLM pipeline falhou (usando fallback): {e}")

        log_decision("NEWS", "news_pipeline", f"eventos={len(news_df)}")

    except Exception as e:
        logger.error(f"Erro no pipeline de noticias: {e}")


def run_forever():
    """
    Loop principal que roda 24/7.
    Sincroniza com fechamento de candles M5.
    """
    setup_logging()
    logger.info("=" * 60)
    logger.info("AutoTrader Prediction System - INICIANDO")
    logger.info("=" * 60)

    with get_mt5_connection() as conn:
        # Valida simbolos
        symbols = validate_symbols(conn)
        logger.info(f"Simbolos ativos: {symbols}")

        # Cria engine
        engine = PredictionEngine(symbols)

        # Scraping inicial de noticias
        _run_news_pipeline()

        # Setup inicial (coleta + treino)
        engine.initial_setup(conn)
        log_decision("SYSTEM", "startup", f"symbols={symbols}")

        # Loop infinito
        cycle = 0
        last_news_run = datetime.utcnow()

        while True:
            try:
                # Espera proximo candle
                wait_for_next_candle()

                # Refresh de noticias no mesmo ritmo do ciclo M5
                now = datetime.utcnow()
                if now - last_news_run >= timedelta(minutes=settings.prediction_interval):
                    _run_news_pipeline()
                    last_news_run = now

                # Roda ciclo
                cycle += 1
                result = engine.run_cycle(conn)

                # Log resumo
                n_symbols = len(result.get("symbols", {}))
                elapsed = result.get("elapsed_seconds", 0)
                logger.info(
                    f"Ciclo {cycle}: {n_symbols} simbolos processados em {elapsed:.1f}s"
                )

            except KeyboardInterrupt:
                logger.info("Interrupcao pelo usuario. Encerrando...")
                log_decision("SYSTEM", "shutdown", "keyboard_interrupt")
                break
            except Exception as e:
                logger.error(f"Erro no ciclo {cycle}: {e}")
                log_decision("SYSTEM", "error", str(e))
                # Espera 30s antes de tentar novamente
                time.sleep(30)


if __name__ == "__main__":
    run_forever()
