"""
Normalizacao de noticias em features estruturadas.
Transforma eventos brutos em formato numerico para modelos ML.

Partes 3, 5 e 6 do pipeline de news.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config.settings import settings
from src.mt5.symbols import COUNTRY_CURRENCY_MAP, get_symbol_currencies

logger = logging.getLogger(__name__)

# Mapeamento signal -> sentiment basico
SIGNAL_SENTIMENT = {
    "good": 1,
    "bad": -1,
    "unknown": 0,
}


def normalize_news(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza noticias brutas em formato estruturado.

    Para cada evento adiciona:
    - currency: moeda ISO mapeada do country
    - impact_num: 1, 2, 3
    - sentiment_basic: +1 (good), -1 (bad), 0 (unknown)
    """
    if df.empty:
        return df

    df = df.copy()

    # Mapear country -> currency
    df["currency"] = df["country"].map(COUNTRY_CURRENCY_MAP).fillna("")

    # Impact numerico (ja e numerico no scraping, mas garante)
    df["impact_num"] = pd.to_numeric(df["impact"], errors="coerce").fillna(0).astype(int)

    # Sentiment basico
    df["sentiment_basic"] = df["signal"].map(SIGNAL_SENTIMENT).fillna(0).astype(int)

    return df


def build_news_features(
    symbol: str,
    current_time: datetime,
    news_df: pd.DataFrame,
    llm_df: pd.DataFrame | None = None,
    post_release_lag_min: int | None = None,
) -> dict:
    """
    Constroi features de noticias para um simbolo em um momento.

    Partes 5 + 6: agrega noticias por moeda base/quote, combina basic + LLM.

    Anti look-ahead bias (opcao C): duas janelas separadas.

    - Ex-ante (schedule e conhecido com antecedencia): impact_num,
      high_impact_flag, minutes_since_last_news. Filtradas por
      timestamp <= current_time.
    - Ex-post (so conhecidas apos release + disseminacao): sentiment_basic
      (greenFont/redFont do actual), LLM sentiment, volatility_impact.
      Filtradas por timestamp + post_release_lag_min <= current_time.

    O `post_release_lag_min` modela a latencia entre a divulgacao oficial
    (timestamp agendado) e o momento em que o scraper/LLM incorporam o
    resultado. Default = settings.news_post_release_lag_min (5 min).

    Args:
        symbol: par forex (ex: EURUSD)
        current_time: momento de referencia
        news_df: DataFrame normalizado de noticias
        llm_df: DataFrame com features LLM (opcional)
        post_release_lag_min: override do lag em minutos (default settings)

    Returns:
        dict com features de noticias para merge no DataFrame principal
    """
    features = _empty_news_features()

    if news_df.empty:
        return features

    base, quote = get_symbol_currencies(symbol)

    lag_min = (
        post_release_lag_min
        if post_release_lag_min is not None
        else settings.news_post_release_lag_min
    )

    # Janela ex-ante: noticias cujo horario agendado ja passou
    window_start = current_time - timedelta(hours=3)
    ex_ante_end = current_time
    # Janela ex-post: noticias cujo resultado ja teve tempo de disseminar
    ex_post_end = current_time - timedelta(minutes=lag_min)

    # Garantir que timestamp e datetime
    if "timestamp" in news_df.columns:
        news_df = news_df.copy()
        news_df["timestamp"] = pd.to_datetime(news_df["timestamp"], errors="coerce")

    ex_ante_mask = (
        (news_df["timestamp"] >= window_start)
        & (news_df["timestamp"] <= ex_ante_end)
    )
    ex_ante_news = news_df[ex_ante_mask]

    ex_post_mask = (
        (news_df["timestamp"] >= window_start)
        & (news_df["timestamp"] <= ex_post_end)
    )
    ex_post_news = news_df[ex_post_mask]

    if ex_ante_news.empty and ex_post_news.empty:
        return features

    # Separar ex-ante por moeda (impact, flag, tempo desde ultima news)
    base_ante = _filter_currency(ex_ante_news, base, is_base=True)
    quote_ante = _filter_currency(ex_ante_news, quote, is_base=False)

    # Separar ex-post por moeda (sentiment pos-release)
    base_post = _filter_currency(ex_post_news, base, is_base=True)
    quote_post = _filter_currency(ex_post_news, quote, is_base=False)

    # --- Features ex-post (sentiment) ---
    features["news_sentiment_base"] = _safe_mean(base_post, "sentiment_basic")
    features["news_sentiment_quote"] = _safe_mean(quote_post, "sentiment_basic")

    # --- Features ex-ante (impact) ---
    features["news_impact_base"] = _safe_sum(base_ante, "impact_num")
    features["news_impact_quote"] = _safe_sum(quote_ante, "impact_num")

    # --- Features LLM (ex-post: LLM processa o actual publicado) ---
    if llm_df is not None and not llm_df.empty:
        llm_merged = _merge_llm_features(ex_post_news, llm_df, base, quote)
        features.update(llm_merged)

    # --- Features temporais (ex-ante: horario agendado) ---
    if not ex_ante_news.empty:
        last_news_time = ex_ante_news["timestamp"].max()
        features["minutes_since_last_news"] = (
            (current_time - last_news_time).total_seconds() / 60.0
        )
    else:
        features["minutes_since_last_news"] = 999.0

    # High impact flag (ex-ante: importancia e publicada antes da release)
    all_relevant_ante = pd.concat([base_ante, quote_ante])
    features["high_impact_flag"] = (
        int((all_relevant_ante["impact_num"] >= 3).any())
        if not all_relevant_ante.empty
        else 0
    )

    # --- Sentiment final (hibrido) ---
    features["news_sentiment_final_base"] = _compute_hybrid_sentiment(
        features["news_sentiment_base"],
        features.get("news_llm_sentiment_base", 0.0),
    )
    features["news_sentiment_final_quote"] = _compute_hybrid_sentiment(
        features["news_sentiment_quote"],
        features.get("news_llm_sentiment_quote", 0.0),
    )

    return features


def _filter_currency(news_df: pd.DataFrame, currency: str, is_base: bool) -> pd.DataFrame:
    """
    Filtra noticias pela moeda. Para XAU como base, inclui currency vazia.
    """
    if news_df.empty:
        return news_df
    if is_base and currency == "XAU":
        return news_df[news_df["currency"].isin(["XAU", ""])]
    return news_df[news_df["currency"] == currency]


def _compute_hybrid_sentiment(basic: float, llm: float) -> float:
    """Combina sentiment: 0.7 * LLM + 0.3 * basic. Fallback para basic se LLM = 0."""
    if llm != 0.0:
        return 0.7 * llm + 0.3 * basic
    return basic


def _merge_llm_features(
    window_news: pd.DataFrame,
    llm_df: pd.DataFrame,
    base: str,
    quote: str,
) -> dict:
    """Merge features LLM com noticias da janela."""
    result = {}

    merge_cols = [col for col in ["timestamp", "name", "country"] if col in window_news.columns and col in llm_df.columns]

    # Join por identificador da noticia para evitar colapsar eventos iguais em paises diferentes
    if merge_cols:
        merged = window_news.merge(
            llm_df[
                merge_cols + [
                    "sentiment_score",
                    "confidence",
                    "volatility_impact",
                    "used_fallback",
                ]
            ],
            on=merge_cols,
            how="left",
        )
    else:
        merged = window_news.copy()
        merged["sentiment_score"] = 0.0
        merged["confidence"] = 0.5
        merged["volatility_impact"] = 0.0
        merged["used_fallback"] = True

    base_m = merged[merged["currency"] == base]
    quote_m = merged[merged["currency"] == quote]

    result["news_llm_sentiment_base"] = _safe_mean(base_m, "sentiment_score")
    result["news_llm_sentiment_quote"] = _safe_mean(quote_m, "sentiment_score")
    result["news_volatility_base"] = _safe_mean(base_m, "volatility_impact")
    result["news_volatility_quote"] = _safe_mean(quote_m, "volatility_impact")

    return result


def _empty_news_features() -> dict:
    """Retorna dict com todas as features de noticias zeradas."""
    return {
        "news_sentiment_base": 0.0,
        "news_sentiment_quote": 0.0,
        "news_impact_base": 0.0,
        "news_impact_quote": 0.0,
        "news_llm_sentiment_base": 0.0,
        "news_llm_sentiment_quote": 0.0,
        "news_volatility_base": 0.0,
        "news_volatility_quote": 0.0,
        "minutes_since_last_news": 999.0,
        "high_impact_flag": 0,
        "news_sentiment_final_base": 0.0,
        "news_sentiment_final_quote": 0.0,
    }


def get_news_feature_columns() -> list[str]:
    """Retorna lista de colunas de features de noticias."""
    return list(_empty_news_features().keys())


def _safe_mean(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    val = df[col].mean()
    return float(val) if pd.notna(val) else 0.0


def _safe_sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    val = df[col].sum()
    return float(val) if pd.notna(val) else 0.0
