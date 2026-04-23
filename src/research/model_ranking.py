"""
Model Ranking Inteligente.
Rankeia modelos com base em metricas financeiras (PnL, Sharpe, Drawdown).
"""

import logging

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)


def rank_models(df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Rankeia modelos com base em score composto.

    Score = pnl - (drawdown * 0.5) + (sharpe * 0.3)

    Args:
        df: DataFrame com resultados de experimentos ou backtest.
            Deve conter colunas: model, pnl, sharpe, drawdown
            Opcionais: accuracy, mae, winrate, symbol, feature_set

    Returns:
        DataFrame ordenado por score (descrescente)
    """
    if df is None:
        df = _load_all_results()

    if df.empty:
        return pd.DataFrame()

    # Garantir colunas numericas
    for col in ["pnl", "sharpe", "drawdown", "accuracy", "mae", "winrate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Calcular score
    df["score"] = (
        df.get("pnl", 0)
        - (df.get("drawdown", 0).abs() * 0.5)
        + (df.get("sharpe", 0) * 0.3)
    )

    # Ranking global (agregar por modelo)
    ranking = df.groupby("model").agg(
        avg_pnl=("pnl", "mean"),
        total_pnl=("pnl", "sum"),
        avg_sharpe=("sharpe", "mean"),
        avg_drawdown=("drawdown", "mean"),
        avg_accuracy=("accuracy", "mean"),
        avg_winrate=("winrate", "mean"),
        avg_score=("score", "mean"),
        best_score=("score", "max"),
        experiments=("score", "count"),
    ).reset_index()

    ranking = ranking.sort_values("avg_score", ascending=False).reset_index(drop=True)
    ranking["rank"] = range(1, len(ranking) + 1)

    # Salvar ranking
    _save_ranking(ranking)

    return ranking


def rank_by_symbol(symbol: str = None) -> pd.DataFrame:
    """Ranking por simbolo especifico."""
    df = _load_all_results()
    if df.empty:
        return pd.DataFrame()

    if symbol:
        df = df[df["symbol"] == symbol]

    return rank_models(df)


def rank_by_feature_set() -> pd.DataFrame:
    """Ranking agregado por feature set."""
    df = _load_all_results()
    if df.empty:
        return pd.DataFrame()

    for col in ["pnl", "sharpe", "drawdown", "accuracy", "mae", "winrate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["score"] = df["pnl"] - (df["drawdown"].abs() * 0.5) + (df["sharpe"] * 0.3)

    ranking = df.groupby("feature_set").agg(
        avg_pnl=("pnl", "mean"),
        avg_sharpe=("sharpe", "mean"),
        avg_drawdown=("drawdown", "mean"),
        avg_accuracy=("accuracy", "mean"),
        avg_score=("score", "mean"),
        models_tested=("model", "nunique"),
    ).reset_index()

    return ranking.sort_values("avg_score", ascending=False).reset_index(drop=True)


def get_best_model(symbol: str = None) -> dict:
    """Retorna o melhor modelo global ou por simbolo."""
    df = _load_all_results()
    if df.empty:
        return {}

    if symbol:
        df = df[df["symbol"] == symbol]

    if df.empty:
        return {}

    for col in ["pnl", "sharpe", "drawdown"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["score"] = df["pnl"] - (df["drawdown"].abs() * 0.5) + (df["sharpe"] * 0.3)

    best = df.loc[df["score"].idxmax()]
    return best.to_dict()


def get_ranking() -> pd.DataFrame:
    """Carrega ranking salvo."""
    ranking_file = settings.data_dir / "experiments" / "ranking.parquet"
    if not ranking_file.exists():
        return rank_models()  # Gerar se nao existe
    return pd.read_parquet(ranking_file)


def _load_all_results() -> pd.DataFrame:
    """Carrega todos os resultados de experimentos + backtest."""
    dfs = []

    # Resultados de feature experiments
    exp_file = settings.data_dir / "experiments" / "results.parquet"
    if exp_file.exists():
        dfs.append(pd.read_parquet(exp_file))

    # Resultados de backtest
    bt_dir = settings.data_dir / "backtest"
    if bt_dir.exists():
        for f in bt_dir.glob("*_metrics.parquet"):
            df = pd.read_parquet(f)
            # Normalizar colunas
            col_map = {"pnl_total": "pnl", "max_drawdown": "drawdown"}
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            if "feature_set" not in df.columns:
                df["feature_set"] = "all"
            if "accuracy" not in df.columns:
                df["accuracy"] = 0
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    return combined


def _save_ranking(ranking: pd.DataFrame) -> None:
    """Salva ranking em parquet."""
    exp_dir = settings.data_dir / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    ranking_file = exp_dir / "ranking.parquet"
    ranking.to_parquet(ranking_file, index=False)
    logger.info(f"Ranking salvo: {len(ranking)} modelos")
