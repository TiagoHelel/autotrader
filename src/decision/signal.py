"""
Decision Layer - Geracao de sinais de trade.
Converte previsoes de modelos ML em sinais actionaveis (BUY/SELL/HOLD).
"""

import logging

from src.utils.logging import log_decision

logger = logging.getLogger(__name__)

# Thresholds default (configuraveis)
DEFAULT_THRESHOLD = 0.0003  # 3 pips para pares 5-digit
DEFAULT_CONFIDENCE_MIN = 0.4

# Session-aware threshold multipliers
# Alta sessao → threshold menor (mais sinais), baixa → threshold maior (menos sinais)
SESSION_THRESHOLD_MAP = {
    # session_score range → threshold multiplier
    "high":   0.7,   # score >= 0.6 → threshold * 0.7 (mais agressivo)
    "medium": 1.0,   # 0.3 <= score < 0.6 → threshold normal
    "low":    1.5,   # score < 0.3 → threshold * 1.5 (mais conservador)
}

# Score minimo para operar (abaixo disso, HOLD)
SESSION_MIN_SCORE = 0.3


def generate_signal(
    predictions: dict,
    current_price: float,
    threshold: float = None,
    confidence_min: float = None,
    session_score: float = None,
) -> dict:
    """
    Gera sinal de trade baseado em previsoes multi-horizonte.

    Args:
        predictions: dict com pred_t1, pred_t2, pred_t3 (precos previstos)
        current_price: preco atual
        threshold: retorno minimo para sinal (default: 0.0003)
        confidence_min: confianca minima para sinal (default: 0.4)
        session_score: score da sessao atual (0-1). Se < 0.3, forca HOLD.

    Returns:
        {
            "signal": "BUY" | "SELL" | "HOLD",
            "confidence": float,
            "expected_return": float,
            "pred_t1": float,
            "pred_t2": float,
            "pred_t3": float,
            "current_price": float,
            "threshold": float,
            "session_score": float | None,
            "session_filtered": bool,
        }
    """
    threshold = threshold or DEFAULT_THRESHOLD
    confidence_min = confidence_min or DEFAULT_CONFIDENCE_MIN

    # Ajustar threshold baseado na sessao
    session_filtered = False
    if session_score is not None:
        if session_score < SESSION_MIN_SCORE:
            session_filtered = True
        elif session_score >= 0.6:
            threshold *= SESSION_THRESHOLD_MAP["high"]
        elif session_score >= 0.3:
            threshold *= SESSION_THRESHOLD_MAP["medium"]
        else:
            threshold *= SESSION_THRESHOLD_MAP["low"]

    pred_t1 = predictions.get("pred_t1", current_price)
    pred_t2 = predictions.get("pred_t2", current_price)
    pred_t3 = predictions.get("pred_t3", current_price)

    # Retornos esperados por horizonte
    ret_t1 = (pred_t1 - current_price) / current_price if current_price > 0 else 0
    ret_t2 = (pred_t2 - current_price) / current_price if current_price > 0 else 0
    ret_t3 = (pred_t3 - current_price) / current_price if current_price > 0 else 0

    # Retorno medio ponderado (t1 pesa mais)
    expected_return = ret_t1 * 0.5 + ret_t2 * 0.3 + ret_t3 * 0.2

    # Confianca baseada na concordancia entre horizontes
    directions = [
        1 if ret_t1 > 0 else (-1 if ret_t1 < 0 else 0),
        1 if ret_t2 > 0 else (-1 if ret_t2 < 0 else 0),
        1 if ret_t3 > 0 else (-1 if ret_t3 < 0 else 0),
    ]
    agreement = abs(sum(directions)) / 3.0
    magnitude = min(abs(expected_return) / threshold, 1.0) if threshold > 0 else 0
    confidence = agreement * 0.6 + magnitude * 0.4

    # Determinar sinal
    if session_filtered:
        signal = "HOLD"
    elif expected_return > threshold and confidence >= confidence_min:
        signal = "BUY"
    elif expected_return < -threshold and confidence >= confidence_min:
        signal = "SELL"
    else:
        signal = "HOLD"

    result = {
        "signal": signal,
        "confidence": round(confidence, 4),
        "expected_return": round(expected_return, 8),
        "pred_t1": float(pred_t1),
        "pred_t2": float(pred_t2),
        "pred_t3": float(pred_t3),
        "current_price": float(current_price),
        "threshold": threshold,
        "session_score": session_score,
        "session_filtered": session_filtered,
    }

    return result


def generate_signals_for_models(
    predictions_by_model: dict,
    current_price: float,
    threshold: float = None,
    session_score: float = None,
) -> dict:
    """
    Gera sinais para todos os modelos de um simbolo.

    Args:
        predictions_by_model: {model_name: [pred_t1, pred_t2, pred_t3]}
        current_price: preco atual
        session_score: score da sessao atual (0-1)

    Returns:
        {model_name: signal_dict}
    """
    signals = {}
    for model_name, preds in predictions_by_model.items():
        if isinstance(preds, dict):
            pred_dict = preds
        elif hasattr(preds, '__len__') and len(preds) >= 3:
            pred_dict = {"pred_t1": preds[0], "pred_t2": preds[1], "pred_t3": preds[2]}
        else:
            continue

        sig = generate_signal(
            pred_dict, current_price,
            threshold=threshold,
            session_score=session_score,
        )
        signals[model_name] = sig

    return signals


def generate_ensemble_signal(
    signals_by_model: dict,
    weights: dict = None,
) -> dict:
    """
    Gera sinal ensemble a partir dos sinais de todos os modelos.
    Votacao ponderada por confianca.

    Args:
        signals_by_model: {model_name: signal_dict}
        weights: pesos por modelo (optional, default=1.0 para todos)

    Returns:
        signal_dict com voto ensemble
    """
    if not signals_by_model:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "expected_return": 0.0,
            "votes": {},
        }

    buy_score = 0.0
    sell_score = 0.0
    hold_score = 0.0
    total_weight = 0.0
    weighted_return = 0.0
    votes = {}

    for model_name, sig in signals_by_model.items():
        w = (weights or {}).get(model_name, 1.0)
        conf = sig.get("confidence", 0.5)
        score = w * conf

        if sig["signal"] == "BUY":
            buy_score += score
        elif sig["signal"] == "SELL":
            sell_score += score
        else:
            hold_score += score

        total_weight += w
        weighted_return += sig.get("expected_return", 0) * w
        votes[model_name] = sig["signal"]

    if total_weight > 0:
        weighted_return /= total_weight

    # Decidir sinal ensemble
    max_score = max(buy_score, sell_score, hold_score)
    if max_score == buy_score and buy_score > sell_score:
        ensemble_signal = "BUY"
    elif max_score == sell_score and sell_score > buy_score:
        ensemble_signal = "SELL"
    else:
        ensemble_signal = "HOLD"

    ensemble_confidence = max_score / total_weight if total_weight > 0 else 0

    return {
        "signal": ensemble_signal,
        "confidence": round(ensemble_confidence, 4),
        "expected_return": round(weighted_return, 8),
        "votes": votes,
        "buy_score": round(buy_score, 4),
        "sell_score": round(sell_score, 4),
        "hold_score": round(hold_score, 4),
    }


def log_signal(symbol: str, model: str, signal_data: dict) -> None:
    """Loga um sinal gerado."""
    details = (
        f"signal={signal_data['signal']} "
        f"conf={signal_data['confidence']:.4f} "
        f"er={signal_data['expected_return']:.6f}"
    )
    log_decision(symbol, f"signal_{model}", details)
    logger.info(f"{symbol} | {model}: {details}")
