"""
Cliente LLM compartilhado (chamadas sincronas, nao-streaming).

Centraliza a chamada HTTP ao provedor (hoje Google Gemini via httpx), retry com
backoff exponencial, e o parsing/reparo de respostas JSON. Os servicos de
dominio (analyzer, requisitos, evaluator, vinculador, verificador, spec_diff)
importam daqui — nenhum deles conhece o provedor diretamente.
"""

import base64
import json
import logging
import re
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        detail = data.get("error", {}).get("message") or response.text
    except Exception:
        detail = response.text

    detail = (detail or "").strip()
    # Keep user-facing message concise.
    if "Please refer to" in detail:
        detail = detail.split("Please refer to", 1)[0].strip()
    return detail


def _parse_retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if not retry_after:
        return None

    try:
        seconds = float(retry_after)
    except ValueError:
        return None

    if seconds <= 0:
        return None

    return seconds


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    header_delay = _parse_retry_after_seconds(response)
    if header_delay is not None:
        return min(header_delay, settings.GEMINI_RETRY_MAX_SECONDS)

    delay = settings.GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
    return min(delay, settings.GEMINI_RETRY_MAX_SECONDS)


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open structures.

    Handles truncation mid-string, mid-key, trailing escapes, and
    incomplete key-value pairs.
    """
    in_string = False
    escape = False
    stack = []

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    # If trailing escape inside string, remove it and close
    if escape:
        text = text[:-1]

    # If we ended inside a string, close it
    if in_string:
        text += '"'

        # After closing string, we might be in an incomplete key-value pair.
        # Find the last structural context to decide what to append.
        stripped = text.rstrip()
        if stripped.endswith('":'):
            # Key without value: add null
            text += ' null'
        elif stripped.endswith(','):
            # Trailing comma: remove it
            text = text.rstrip()[:-1]

    # Remove any trailing commas before closing
    text = text.rstrip()
    if text.endswith(','):
        text = text[:-1]

    # Close any remaining open structures
    for opener in reversed(stack):
        text += ']' if opener == '[' else '}'

    return text


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling possible markdown code blocks."""
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed (%s), attempting repair", e)
        try:
            repaired = _repair_truncated_json(text)
            return json.loads(repaired)
        except json.JSONDecodeError:
            logger.warning("Repair failed, truncating to last complete item")
            # Last resort: find the last complete item in the array and close
            last_brace = text.rfind('},')
            if last_brace > 0:
                truncated = text[:last_brace + 1]
                truncated = _repair_truncated_json(truncated)
                return json.loads(truncated)
            raise


def call_llm(
    system: str,
    user_content: str,
    *,
    temperature: float = 0.1,
    max_output_tokens: int = 65536,
    model: str | None = None,
) -> str:
    """Call the LLM API and return the text response.

    `model` overrides settings.GEMINI_MODEL for this call only — used by the
    cross-item verifier to run a stronger (Pro) model on flagged items without
    changing the model of the whole analysis.
    """
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    model_name = (model or settings.GEMINI_MODEL).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    max_attempts = max(1, settings.GEMINI_MAX_RETRIES)
    response = None

    with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.post(url, params={"key": api_key}, json=payload)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                if attempt < max_attempts:
                    wait_seconds = min(
                        settings.GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                        settings.GEMINI_RETRY_MAX_SECONDS,
                    )
                    logger.warning(
                        "LLM API timeout (tentativa %d/%d). Nova tentativa em %.1fs. Erro: %s",
                        attempt,
                        max_attempts,
                        wait_seconds,
                        exc,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"LLM API timeout apos {max_attempts} tentativas: {exc}") from exc

            if response.status_code < 400:
                break

            detail = _extract_error_detail(response)
            is_retryable = response.status_code in RETRYABLE_STATUS_CODES
            if is_retryable and attempt < max_attempts:
                wait_seconds = _retry_delay_seconds(response, attempt)
                logger.warning(
                    "LLM API erro %d (tentativa %d/%d). Nova tentativa em %.1fs. Detalhe: %s",
                    response.status_code,
                    attempt,
                    max_attempts,
                    wait_seconds,
                    detail,
                )
                time.sleep(wait_seconds)
                continue
            break

    if response is None:
        raise RuntimeError("Falha ao inicializar chamada da LLM API")

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        if response.status_code == 429:
            raise RuntimeError(
                "LLM API indisponivel por limite temporario (429). "
                "Aguarde alguns instantes e tente novamente."
            )
        raise RuntimeError(f"Erro LLM API ({response.status_code}): {detail}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("LLM API retornou resposta sem candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()

    if not text:
        finish_reason = candidates[0].get("finishReason")
        raise RuntimeError(
            f"LLM API retornou resposta vazia (finishReason={finish_reason})"
        )

    finish_reason = candidates[0].get("finishReason")
    if finish_reason == "MAX_TOKENS":
        logger.warning(
            "LLM response truncated (MAX_TOKENS). Response length: %d chars. "
            "Will attempt JSON repair.",
            len(text),
        )

    return text


def call_llm_multimodal(
    system: str,
    user_text: str,
    imagens: list[tuple[str, bytes]],
    *,
    temperature: float = 0.0,
    max_output_tokens: int = 8192,
    model: str | None = None,
) -> str:
    """Chamada multimodal (texto + imagens) ao Gemini — usada para OCR/transcricao.

    `imagens`: lista de (mime_type, bytes). Cada imagem vira uma part inline_data.
    Reutiliza o mesmo retry/backoff do call_llm para 429/5xx/timeout.
    """
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    model_name = (model or settings.GEMINI_MODEL).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
    )
    parts: list[dict] = [{"text": user_text}]
    for mime, data in imagens:
        parts.append(
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
        )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    max_attempts = max(1, settings.GEMINI_MAX_RETRIES)
    response = None
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.post(url, params={"key": api_key}, json=payload)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                if attempt < max_attempts:
                    time.sleep(min(
                        settings.GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                        settings.GEMINI_RETRY_MAX_SECONDS,
                    ))
                    continue
                raise RuntimeError(f"LLM multimodal timeout: {exc}") from exc
            if response.status_code < 400:
                break
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                time.sleep(_retry_delay_seconds(response, attempt))
                continue
            break

    if response is None or response.status_code >= 400:
        detail = _extract_error_detail(response) if response is not None else "sem resposta"
        raise RuntimeError(f"Erro LLM multimodal ({getattr(response, 'status_code', '?')}): {detail}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    parts_out = candidates[0].get("content", {}).get("parts", [])
    return "".join(
        p.get("text", "") for p in parts_out if isinstance(p, dict) and isinstance(p.get("text"), str)
    ).strip()
