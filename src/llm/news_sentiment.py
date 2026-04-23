"""
Analise de sentimento de noticias via LLM local (Qwen 3.5 9B).

Endpoint unico HTTP compativel com OpenAI Chat Completions. Se o backend
local falhar (offline, timeout, resposta invalida), cai direto para
`_fallback_sentiment` (heuristica neutra com `used_fallback=True`).

Historicamente existia cadeia de fallback com endpoints RunPod — foi
removida em 2026-04-17 por decisao de simplificacao (LLM 1 e LLM 2
retirados, mantido apenas o LLM local).
"""

import json
import logging
import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import httpx

from config.settings import settings

# Sinalizado pelo lifespan do FastAPI no shutdown. Processamento LLM em batch
# checa antes de cada noticia para abortar rapido em Ctrl+C.
shutdown_event = threading.Event()


class LLMShutdown(Exception):
    """Erro levantado quando o servico esta desligando durante processamento LLM."""

logger = logging.getLogger(__name__)

# Cache em memoria de resultados LLM (hash do texto -> resultado)
_llm_cache: dict[str, dict] = {}
_backend_cooldowns: dict[str, datetime] = {}
# Modos de API marcados como "quebrados" para um backend nesta sessao.
# Chave: backend.name, valor: set de (attempt_kind, no_think) a pular.
# Evita retentar /responses a cada noticia quando ele sempre retorna so reasoning.
_backend_skip_modes: dict[str, set[tuple[str, bool]]] = {}

# Diretorio para persistencia
LLM_FEATURES_DIR = settings.data_dir / "news"
BACKEND_COOLDOWN_SECONDS = 300

# Prompt template
LLM_PROMPT = """Classifique esta noticia economica para trading FX/commodities:

Retorne JSON com:
- sentiment_score (-1 bearish, +1 bullish)
- confidence (0-1)
- event_type (interest_rate, inflation, employment, gdp, trade_balance, housing, manufacturing, consumer, other)
- volatility_impact (0-1)
- reasoning_short (resumo curto de 3 a 12 palavras)

Responda APENAS com o JSON, sem texto adicional.

Noticia: {text}"""


@dataclass(frozen=True)
class LLMBackend:
    name: str
    api_url: str
    api_key: str
    model: str
    api_kind: str = "chat-completions"


def _configured_backends() -> list[LLMBackend]:
    """Retorna a lista de backends LLM configurados.

    Agora apenas o backend local (Qwen 3.5 9B). Se `api_url` nao estiver
    configurada, retorna lista vazia e o pipeline cai direto na heuristica.
    """
    candidates = [
        LLMBackend(
            name="local_qwen",
            api_url=settings.llm.api_url,
            api_key=settings.llm.api_key,
            model=settings.llm.model,
            api_kind=settings.llm.api_kind,
        ),
    ]
    return [backend for backend in candidates if backend.api_url and backend.model]


def get_llm_sentiment(news_text: str) -> dict:
    """
    Analisa sentimento de uma noticia usando LLM local via HTTP.

    Args:
        news_text: texto da noticia

    Returns:
        dict com: sentiment_score, confidence, event_type, volatility_impact
    """
    # Check cache
    text_hash = hashlib.md5(news_text.encode()).hexdigest()
    if text_hash in _llm_cache:
        return _llm_cache[text_hash]

    # Tentar cadeia principal -> fallbacks
    try:
        result = _call_llm_with_failover(news_text)
        _llm_cache[text_hash] = result
        return result
    except Exception as e:
        logger.warning(f"LLM falhou, usando fallback: {e}")
        return _fallback_sentiment(news_text)


def _call_llm_with_failover(news_text: str) -> dict:
    """Tenta cada backend configurado ate obter uma resposta valida."""
    errors = []
    backends = _configured_backends()
    if not backends:
        raise ValueError("Nenhum backend LLM configurado")

    available_backends = [backend for backend in backends if not _backend_in_cooldown(backend)]
    if not available_backends:
        raise RuntimeError("Todos os backends LLM estao em cooldown")

    for backend in available_backends:
        try:
            logger.debug(f"Tentando LLM backend={backend.name} kind={backend.api_kind}")
            result = _call_backend(news_text, backend)
            _clear_backend_cooldown(backend)
            result["llm_backend"] = backend.name
            return result
        except Exception as exc:
            error_msg = f"{backend.name}: {exc}"
            errors.append(error_msg)
            _mark_backend_unavailable(backend, exc)
            logger.warning(f"Backend LLM indisponivel ({error_msg})")

    raise RuntimeError("Todos os backends LLM falharam: " + " | ".join(errors))


def _is_sticky_failure(exc: Exception) -> bool:
    """Identifica erros que refletem incompatibilidade da API (nao transientes).

    "Apenas reasoning sem output_text" indica que o modelo/endpoint nao suporta
    o modo — nao adianta retentar. Ja timeouts/5xx sao transientes.
    """
    msg = str(exc).lower()
    return (
        "apenas reasoning" in msg
        or "resposta vazia" in msg
    )


def _call_backend(news_text: str, backend: LLMBackend) -> dict:
    """Chama um backend especifico via HTTP, com retries por compatibilidade."""
    api_kind = (backend.api_kind or "chat-completions").strip().lower()
    attempts: list[tuple[str, bool]] = []

    if api_kind == "openai-responses":
        attempts.append(("openai-responses", False))
        attempts.append(("chat-completions", True))
    else:
        attempts.append(("chat-completions", False))
        attempts.append(("chat-completions", True))

    skip = _backend_skip_modes.get(backend.name, set())
    attempts = [a for a in attempts if a not in skip]
    if not attempts:
        # Todos os modos marcados como quebrados; esvazia p/ permitir nova
        # tentativa (caso o backend tenha sido corrigido).
        _backend_skip_modes.pop(backend.name, None)
        attempts = [("chat-completions", True)]

    errors = []
    for attempt_kind, no_think in attempts:
        try:
            data = _post_to_backend(news_text, backend, attempt_kind, no_think=no_think)
            content = _extract_content(data, attempt_kind)
            result = _parse_llm_response(content)
            return _validate_result(result)
        except Exception as exc:
            mode = f"{attempt_kind}{' no_think' if no_think else ''}"
            errors.append(f"{mode}: {exc}")
            # Demotado de warning -> debug: falha em uma tentativa especifica e
            # esperada quando ha fallback interno (outro modo) ou fallback de
            # backend. O log externo de `_call_llm_with_failover` ja sinaliza
            # backend indisponivel quando todos os modos falham.
            logger.debug(f"Falha no backend={backend.name} modo={mode}: {exc}")
            # Modos que falham por incompatibilidade da API nao devem ser
            # retentados nesta sessao — economiza ~5s por noticia.
            if _is_sticky_failure(exc):
                bucket = _backend_skip_modes.setdefault(backend.name, set())
                if (attempt_kind, no_think) not in bucket:
                    bucket.add((attempt_kind, no_think))
                    logger.info(
                        f"Backend {backend.name} modo={mode} desativado nesta sessao "
                        f"(incompativel): {exc}"
                    )

    raise RuntimeError(" | ".join(errors))


def _backend_in_cooldown(backend: LLMBackend) -> bool:
    until = _backend_cooldowns.get(backend.name)
    if until is None:
        return False
    if datetime.utcnow() >= until:
        _backend_cooldowns.pop(backend.name, None)
        return False
    return True


def _mark_backend_unavailable(backend: LLMBackend, exc: Exception) -> None:
    cooldown_until = datetime.utcnow() + timedelta(seconds=BACKEND_COOLDOWN_SECONDS)
    previous = _backend_cooldowns.get(backend.name)
    _backend_cooldowns[backend.name] = cooldown_until
    if previous is None or cooldown_until > previous:
        logger.warning(
            f"Backend {backend.name} em cooldown por {BACKEND_COOLDOWN_SECONDS}s apos erro: {exc}"
        )


def _clear_backend_cooldown(backend: LLMBackend) -> None:
    _backend_cooldowns.pop(backend.name, None)


def _all_backends_in_cooldown() -> bool:
    backends = _configured_backends()
    return bool(backends) and all(_backend_in_cooldown(backend) for backend in backends)


def _post_to_backend(
    news_text: str,
    backend: LLMBackend,
    api_kind: str,
    *,
    no_think: bool = False,
) -> dict:
    """Envia request para um backend em um modo especifico."""
    base_url = backend.api_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
    }
    if backend.api_key:
        headers["Authorization"] = f"Bearer {backend.api_key}"

    prompt = LLM_PROMPT.format(text=news_text)
    disable_thinking = settings.llm.disable_thinking or no_think
    if disable_thinking:
        prompt = "/no_think " + prompt

    if api_kind == "openai-responses":
        url = f"{base_url}/responses"
        payload = {
            "model": backend.model,
            "input": prompt,
            "temperature": 0.1,
            "max_output_tokens": 400,
        }
        if disable_thinking:
            payload["reasoning"] = {"effort": "none"}
    else:
        url = f"{base_url}/chat/completions"
        payload = {
            "model": backend.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.1,
            "max_tokens": 400,
        }
        if disable_thinking:
            payload["reasoning"] = {"effort": "none"}

    # Timeout reduzido: connect curto, read ate 20s. Evita travar shutdown
    # por minutos quando o backend LLM esta lento/offline.
    timeout = httpx.Timeout(20.0, connect=5.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    return response.json()


def _extract_content(data: dict, api_kind: str) -> str:
    """Extrai texto retornado por Responses API ou Chat Completions."""
    if api_kind == "openai-responses":
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text", "")
                    if text:
                        return str(text).strip()
        reasoning_fragments = []
        for item in data.get("output", []):
            if item.get("type") == "reasoning":
                for summary in item.get("summary", []):
                    text = summary.get("text")
                    if text:
                        reasoning_fragments.append(str(text).strip())
        if reasoning_fragments:
            raise ValueError("Responses API retornou apenas reasoning sem output_text")
        raise ValueError("Resposta vazia da Responses API")

    message = data["choices"][0]["message"]
    content = message.get("content", "")
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                text = item.get("text", "")
                if text:
                    chunks.append(str(text))
        content = "\n".join(chunks).strip()
    else:
        content = str(content).strip()

    if content:
        return content

    if message.get("reasoning"):
        raise ValueError("Chat Completions retornou apenas reasoning sem content")
    raise ValueError("Resposta vazia da Chat Completions API")


def _parse_llm_response(content: str) -> dict:
    """Faz parse da resposta do LLM, lidando com markdown code blocks."""
    # Remove markdown code blocks se presentes
    if "```" in content:
        lines = content.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block or not content.startswith("```"):
                json_lines.append(line)
        content = "\n".join(json_lines)

    # Tenta achar JSON no texto
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        content = content[start:end]

    return json.loads(content)


def _validate_result(result: dict) -> dict:
    """Valida e normaliza resultado do LLM."""
    return {
        "sentiment_score": max(-1.0, min(1.0, float(result.get("sentiment_score", 0.0)))),
        "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.5)))),
        "event_type": str(result.get("event_type", "other")),
        "volatility_impact": max(0.0, min(1.0, float(result.get("volatility_impact", 0.0)))),
        "reasoning_short": str(result.get("reasoning_short", "")).strip()[:120],
        "used_fallback": False,
        "llm_backend": str(result.get("llm_backend", "")),
    }


def _fallback_sentiment(news_text: str) -> dict:
    """Fallback quando LLM falha: usa heuristicas simples."""
    return {
        "sentiment_score": 0.0,
        "confidence": 0.5,
        "event_type": "other",
        "volatility_impact": 0.3,
        "reasoning_short": "fallback",
        "used_fallback": True,
        "llm_backend": "heuristic_fallback",
    }


def process_news_with_llm(news_df: pd.DataFrame) -> pd.DataFrame:
    """
    Processa DataFrame de noticias e adiciona features LLM.
    Usa cache para evitar chamadas repetidas.

    Args:
        news_df: DataFrame normalizado de noticias

    Returns:
        DataFrame com colunas LLM adicionadas
    """
    if news_df.empty:
        return news_df

    results = []
    skip_remote_for_batch = _all_backends_in_cooldown()
    for _, row in news_df.iterrows():
        if shutdown_event.is_set():
            logger.info("LLM batch abortado: shutdown sinalizado")
            raise LLMShutdown()
        # Construir texto para LLM
        text_parts = []
        if row.get("name"):
            text_parts.append(f"Event: {row['name']}")
        if row.get("country"):
            text_parts.append(f"Country: {row['country']}")
        if row.get("currency"):
            text_parts.append(f"Currency: {row['currency']}")
        if row.get("impact_num") is not None:
            text_parts.append(f"Impact: {row.get('impact_num')}/3")
        if row.get("signal"):
            text_parts.append(f"Basic signal: {row['signal']}")
        if row.get("event_type") and str(row.get("event_type")) not in ("None", ""):
            text_parts.append(f"Event type: {row['event_type']}")
        if row.get("actual"):
            text_parts.append(f"Actual: {row['actual']}")
        if row.get("forecast"):
            text_parts.append(f"Forecast: {row['forecast']}")
        if row.get("previous"):
            text_parts.append(f"Previous: {row['previous']}")

        news_text = " | ".join(text_parts)
        if skip_remote_for_batch:
            llm_result = _fallback_sentiment(news_text)
        else:
            llm_result = get_llm_sentiment(news_text)
            if llm_result.get("used_fallback") and _all_backends_in_cooldown():
                skip_remote_for_batch = True

        results.append({
            "timestamp": row.get("timestamp"),
            "name": row.get("name"),
            "country": row.get("country"),
            "currency": row.get("currency"),
            **llm_result,
        })

    llm_df = pd.DataFrame(results)
    return llm_df


def save_llm_features(llm_df: pd.DataFrame) -> Path:
    """Salva features LLM em parquet."""
    LLM_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = LLM_FEATURES_DIR / "llm_features.parquet"

    if filepath.exists():
        existing = pd.read_parquet(filepath)
        combined = pd.concat([existing, llm_df], ignore_index=True)
        dedup_cols = [
            col for col in ["timestamp", "name", "country"] if col in combined.columns
        ]
        if dedup_cols:
            combined = combined.drop_duplicates(
                subset=dedup_cols, keep="last"
            )
        llm_df = combined

    llm_df.to_parquet(filepath, index=False)
    logger.info(f"LLM features salvas: {filepath} ({len(llm_df)} rows)")
    return filepath


def load_llm_features() -> pd.DataFrame:
    """Carrega features LLM do parquet."""
    filepath = LLM_FEATURES_DIR / "llm_features.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)
