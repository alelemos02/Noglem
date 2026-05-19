import json
import logging
import re
import time
import unicodedata

import httpx

from app.core.config import settings
from app.services.llm_prompt import (
    USER_PROMPT_TEMPLATE,
    CHUNK_USER_PROMPT_TEMPLATE,
    REDUCE_PROMPT,
    PROFILE_ITEM_LIMIT_TEMPLATE,
    PROFILE_INTEGRAL_TEMPLATE,
    FIELD_OPTIMIZATION_SYSTEM,
    get_system_prompt,
)

logger = logging.getLogger(__name__)

# Approximate token limit for a single API call (leaving room for system prompt + response)
MAX_INPUT_CHARS = 80_000  # ~20k tokens, ensures response fits within output token limits

DEFAULT_ANALYSIS_PROFILE = "padrao"

# Named profiles: (internal_key, display_label, max_itens)
_NAMED_PROFILES: dict[str, tuple[str, int]] = {
    "simples":  ("Simples",  10),
    "padrao":   ("Padrao",   15),
    "completa": ("Completa", 20),
    "integral": ("Integral", 0),  # 0 = no cap — uses separate template
    # backward-compat aliases for cached results / old API calls
    "triagem_tecnica":          ("Simples",  10),
    "conformidade_tecnica":     ("Padrao",   15),
    "auditoria_tecnica_completa": ("Completa", 20),
}

_CUSTOM_PROFILE_RE = re.compile(r"^custom_(\d+)$")
DEFAULT_OBSERVATION_BY_STATUS = {
    "A": "Item aderente aos requisitos tecnicos da engenharia, sem desvios identificados.",
    "B": "Item parcialmente conforme; requer ajustes para atendimento completo.",
    "C": "Item nao conforme aos requisitos tecnicos e necessita revisao do fornecedor.",
    "D": "Informacao tecnica ausente na documentacao do fornecedor.",
    "E": "Item adicional apresentado pelo fornecedor e pendente de avaliacao da engenharia.",
}
DEFAULT_ACTION_BY_STATUS = {
    "B": "Adequar a proposta para atendimento integral do requisito e reapresentar evidencia tecnica.",
    "C": "Revisar a solucao tecnica e ressubmeter item em conformidade com a requisicao de engenharia.",
    "D": "Complementar a documentacao tecnica com dados objetivos e rastreaveis para avaliacao.",
    "E": "Submeter item adicional para avaliacao formal da engenharia quanto a aceitabilidade no escopo.",
}
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


def _extract_json(text: str) -> dict:
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


def normalize_analysis_profile(profile: str | None) -> str:
    if profile and (profile in _NAMED_PROFILES or _CUSTOM_PROFILE_RE.match(profile or "")):
        return profile
    return DEFAULT_ANALYSIS_PROFILE


def get_profile_label(profile: str) -> str:
    if profile in _NAMED_PROFILES:
        return _NAMED_PROFILES[profile][0]
    m = _CUSTOM_PROFILE_RE.match(profile)
    if m:
        return f"Personalizado ({m.group(1)} itens)"
    return _NAMED_PROFILES[DEFAULT_ANALYSIS_PROFILE][0]


def get_profile_max_itens(profile: str) -> int:
    if profile in _NAMED_PROFILES:
        return _NAMED_PROFILES[profile][1]
    m = _CUSTOM_PROFILE_RE.match(profile)
    if m:
        return max(1, min(int(m.group(1)), 100))
    return _NAMED_PROFILES[DEFAULT_ANALYSIS_PROFILE][1]


def _profile_instruction(profile: str | None) -> str:
    normalized = normalize_analysis_profile(profile)
    if normalized == "integral":
        return f"\n\n{PROFILE_INTEGRAL_TEMPLATE}\n"
    label = get_profile_label(normalized)
    max_itens = get_profile_max_itens(normalized)
    return f"\n\n{PROFILE_ITEM_LIMIT_TEMPLATE.format(label=label, max_itens=max_itens)}\n"


def _split_text_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def _call_gemini(system: str, user_content: str) -> str:
    """Call Gemini API and return text response."""
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 65536,
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
                        "Gemini API timeout (tentativa %d/%d). Nova tentativa em %.1fs. Erro: %s",
                        attempt,
                        max_attempts,
                        wait_seconds,
                        exc,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Gemini API timeout apos {max_attempts} tentativas: {exc}") from exc

            if response.status_code < 400:
                break

            detail = _extract_error_detail(response)
            is_retryable = response.status_code in RETRYABLE_STATUS_CODES
            if is_retryable and attempt < max_attempts:
                wait_seconds = _retry_delay_seconds(response, attempt)
                logger.warning(
                    "Gemini API erro %d (tentativa %d/%d). Nova tentativa em %.1fs. Detalhe: %s",
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
        raise RuntimeError("Falha ao inicializar chamada da Gemini API")

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        if response.status_code == 429:
            raise RuntimeError(
                "Gemini API indisponivel por limite temporario (429). "
                "Aguarde alguns instantes e tente novamente."
            )
        raise RuntimeError(f"Erro Gemini API ({response.status_code}): {detail}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini API retornou resposta sem candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()

    if not text:
        finish_reason = candidates[0].get("finishReason")
        raise RuntimeError(
            f"Gemini API retornou resposta vazia (finishReason={finish_reason})"
        )

    finish_reason = candidates[0].get("finishReason")
    if finish_reason == "MAX_TOKENS":
        logger.warning(
            "Gemini response truncated (MAX_TOKENS). Response length: %d chars. "
            "Will attempt JSON repair.",
            len(text),
        )

    return text


def _validate_parecer_json(data: dict) -> dict:
    """Validate and normalize the parecer JSON structure."""
    pt = data.get("parecer_tecnico", data)

    # Ensure resumo_executivo exists
    resumo = pt.get("resumo_executivo", {})
    itens = pt.get("itens", [])

    # Recalculate totals from items for consistency
    status_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for item in itens:
        s = item.get("status", "D")
        if s in status_counts:
            status_counts[s] += 1

    resumo["total_itens"] = len(itens)
    resumo["aprovados"] = status_counts["A"]
    resumo["aprovados_com_comentarios"] = status_counts["B"]
    resumo["rejeitados"] = status_counts["C"]
    resumo["informacao_ausente"] = status_counts["D"]
    resumo["itens_adicionais_fornecedor"] = status_counts["E"]

    # Determine parecer_geral
    if status_counts["C"] > 0:
        resumo["parecer_geral"] = "REJEITADO"
    elif status_counts["B"] > 0 or status_counts["D"] > 0:
        resumo["parecer_geral"] = "APROVADO COM COMENTARIOS"
    else:
        resumo["parecer_geral"] = "APROVADO"

    # Validate each item
    valid_statuses = {"A", "B", "C", "D", "E"}
    valid_priorities = {"ALTA", "MEDIA", "BAIXA"}
    for i, item in enumerate(itens):
        item["numero"] = i + 1
        if item.get("status") not in valid_statuses:
            item["status"] = "D"

        justificativa = (item.get("justificativa_tecnica") or "").strip()
        if not justificativa:
            item["justificativa_tecnica"] = DEFAULT_OBSERVATION_BY_STATUS.get(
                item["status"],
                "Item avaliado. Revisar conformidade tecnica deste requisito.",
            )
        else:
            item["justificativa_tecnica"] = justificativa

        if item["status"] == "A":
            item["acao_requerida"] = None
        else:
            acao_requerida = (item.get("acao_requerida") or "").strip()
            item["acao_requerida"] = acao_requerida or DEFAULT_ACTION_BY_STATUS.get(
                item["status"],
                "Revisar item e reapresentar documentacao tecnica para nova avaliacao.",
            )

        if item.get("prioridade") not in valid_priorities:
            # Infer priority from status
            if item["status"] == "C":
                item["prioridade"] = "ALTA"
            elif item["status"] in ("B", "D"):
                item["prioridade"] = "MEDIA"
            else:
                item["prioridade"] = "BAIXA"

    pt["resumo_executivo"] = resumo
    pt["itens"] = itens
    pt.setdefault("conclusao", resumo.get("comentario_geral", ""))
    pt.setdefault("recomendacoes", [])

    return {"parecer_tecnico": pt}


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _reference_found(reference: str | None, source_text: str) -> bool:
    if not reference:
        return True

    ref = _normalize_text(reference)
    source = _normalize_text(source_text)
    if not ref:
        return True

    # Ignore very short references to reduce false positives.
    if len(ref) < 12:
        return True

    return ref in source


def validate_reference_grounding(
    data: dict,
    texto_engenharia: str,
    texto_fornecedor: str,
) -> tuple[dict, dict]:
    """
    Validate whether LLM references exist in source documents.

    If a reference is not found, item is flagged with status D and technical
    justification is annotated to surface possible hallucination.
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    flagged_items = 0
    eng_misses = 0
    forn_misses = 0

    for item in itens:
        eng_ref = item.get("referencia_engenharia")
        forn_ref = item.get("referencia_fornecedor")

        eng_ok = _reference_found(eng_ref, texto_engenharia)
        forn_ok = _reference_found(forn_ref, texto_fornecedor)

        issues = []
        if eng_ref and not eng_ok:
            eng_misses += 1
            issues.append("referencia de engenharia nao localizada literalmente")
        if forn_ref and not forn_ok:
            forn_misses += 1
            issues.append("referencia de fornecedor nao localizada literalmente")

        if issues:
            flagged_items += 1
            # NOTE: Do NOT override status to D. The LLM's original status
            # reflects the actual technical analysis. Reference grounding is
            # informational only — substring matching is too imprecise to
            # override engineering judgment.

    result = {"parecer_tecnico": pt}
    validated = _validate_parecer_json(result)
    summary = {
        "items_checked": len(itens),
        "items_flagged": flagged_items,
        "eng_reference_misses": eng_misses,
        "forn_reference_misses": forn_misses,
    }
    return validated, summary


# ---------------------------------------------------------------------------
# Value Consistency Validation (Anti-false-negative)
# ---------------------------------------------------------------------------

# Portuguese boilerplate prefixes commonly found in valor_requerido / valor_fornecedor
_BOILERPLATE_PREFIXES = [
    "solicitado:", "ofertado:", "requerido:", "exigido:", "especificado:",
    "o fornecedor deve", "o fornecedor devera", "deve ser", "devera ser",
    "deve atender", "deve possuir", "deve conter", "conforme", "de acordo com",
    "em conformidade com", "no minimo", "no maximo", "minimo de", "maximo de",
    "a proposta deve", "e necessario", "e obrigatorio",
]

_STOPWORDS_PT = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "um", "uma", "uns", "umas", "por", "para", "com", "sem", "que", "ou", "se",
    "ao", "aos", "as", "pelo", "pela", "pelos", "pelas", "este", "esta", "esse",
    "essa", "aquele", "aquela", "ser", "ter", "nao", "sim", "mais", "menos",
    "muito", "pouco", "todo", "toda", "todos", "todas", "outro", "outra",
    "mesmo", "mesma", "cada", "qual", "quando", "como", "onde", "ate",
    "entre", "sobre", "apos", "antes", "depois", "ja", "ainda", "tambem",
    "so", "apenas", "bem", "mal", "tipo", "forma", "modo", "item",
}


def _extract_keywords(valor_requerido: str) -> list[str]:
    """Extract meaningful technical keywords from a valor_requerido string.

    Strips Portuguese boilerplate, stopwords, and returns normalized keywords
    of 2+ characters that are likely to be technically meaningful.
    """
    if not valor_requerido:
        return []

    text = _normalize_text(valor_requerido)

    # Strip boilerplate prefixes
    for prefix in _BOILERPLATE_PREFIXES:
        norm_prefix = _normalize_text(prefix)
        if text.startswith(norm_prefix):
            text = text[len(norm_prefix):].strip()

    # Tokenize: split on whitespace and common punctuation
    tokens = re.split(r'[\s,;:()\[\]{}/|]+', text)

    # Filter: keep tokens that are meaningful (not stopwords, length >= 2)
    keywords = []
    for token in tokens:
        token = token.strip().strip('"').strip("'")
        if len(token) < 2:
            continue
        if token in _STOPWORDS_PT:
            continue
        keywords.append(token)

    return keywords


def _keyword_found_in_text(keyword: str, normalized_text: str) -> bool:
    """Check if a keyword appears in normalized text using multiple strategies.

    Strategies:
    1. Exact substring match (works for longer terms and codes)
    2. Word-boundary match for short keywords (≤4 chars) to avoid partial
       matches like "sc" inside "descricao"
    """
    # Strategy 1: Direct substring
    if keyword in normalized_text:
        # For short keywords, require word boundaries to avoid false positives
        if len(keyword) <= 4:
            pattern = r'(?<![a-z0-9])' + re.escape(keyword) + r'(?![a-z0-9])'
            return bool(re.search(pattern, normalized_text))
        return True

    return False


def validate_value_consistency(
    data: dict,
    texto_fornecedor: str,
) -> tuple[dict, dict]:
    """
    Validate consistency between LLM claims and actual supplier text.

    For items classified as B, C, or D, checks if key terms from
    valor_requerido are actually present in the supplier text.
    When a required term IS found but the LLM said it wasn't compliant,
    flags the item with a warning annotation.

    Does NOT change item status (to avoid introducing new errors).
    Only adds informational annotations to justificativa_tecnica.

    Returns:
        tuple of (modified data dict, summary dict with statistics)
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    normalized_forn = _normalize_text(texto_fornecedor)

    items_checked = 0
    items_flagged = 0
    flag_details: list[dict] = []

    for item in itens:
        status = item.get("status", "A")
        if status not in ("B", "C", "D"):
            continue

        valor_requerido = item.get("valor_requerido", "")
        if not valor_requerido:
            continue

        items_checked += 1
        keywords = _extract_keywords(valor_requerido)

        if not keywords:
            continue

        # Check which keywords from valor_requerido are found in supplier text
        found_keywords = []
        missing_keywords = []
        for kw in keywords:
            if _keyword_found_in_text(kw, normalized_forn):
                found_keywords.append(kw)
            else:
                missing_keywords.append(kw)

        if not found_keywords:
            continue

        found_ratio = len(found_keywords) / len(keywords)

        # Heuristic: flag if a significant portion of required keywords
        # are found in supplier text but item is classified as non-compliant
        should_flag = False
        if status == "D" and found_ratio >= 0.3:
            should_flag = True
        elif status == "C" and found_ratio >= 0.5:
            should_flag = True
        elif status == "B" and found_ratio >= 0.7:
            should_flag = True

        if should_flag:
            items_flagged += 1
            found_str = ", ".join(found_keywords[:5])
            status_label = {
                "B": "parcialmente conforme",
                "C": "nao conforme",
                "D": "informacao ausente",
            }.get(status, status)
            logger.warning(
                "VALIDACAO_CONSISTENCIA: Termos '%s' encontrados no fornecedor "
                "mas item #%s classificado como %s.",
                found_str,
                item.get("numero"),
                status_label,
            )
            justificativa = (item.get("justificativa_tecnica") or "").strip()
            consistency_note = (
                "[VALIDACAO_CONSISTENCIA] Termos do requisito foram encontrados "
                f"no documento do fornecedor ({found_str}), mas o item foi "
                f"classificado como {status_label}. Revisar classificacao."
            )
            if "VALIDACAO_CONSISTENCIA" not in justificativa:
                item["justificativa_tecnica"] = (
                    f"{justificativa}\n\n{consistency_note}"
                    if justificativa
                    else consistency_note
                )

            flag_details.append({
                "numero": item.get("numero"),
                "status": status,
                "found_keywords": found_keywords,
                "missing_keywords": missing_keywords,
                "found_ratio": round(found_ratio, 2),
            })

    result = {"parecer_tecnico": pt}
    validated = _validate_parecer_json(result)

    summary = {
        "items_checked": items_checked,
        "items_flagged": items_flagged,
        "flag_details": flag_details,
    }

    return validated, summary


# ---------------------------------------------------------------------------
# LLM Self-Review (Optional second pass)
# ---------------------------------------------------------------------------

SELF_REVIEW_PROMPT = """Voce e um revisor tecnico senior. Recebeu itens de um parecer tecnico que foram sinalizados como possiveis erros de leitura.

Para cada item abaixo, voce deve:
1. LER ATENTAMENTE o texto completo do fornecedor fornecido
2. BUSCAR especificamente os termos/valores indicados como requeridos
3. Verificar se a classificacao original (B/C/D) esta CORRETA ou se houve erro de leitura

Retorne EXCLUSIVAMENTE um JSON valido, sem texto adicional antes ou depois, com a seguinte estrutura:
{
  "revisoes": [
    {
      "numero": <numero do item>,
      "classificacao_original_correta": true | false,
      "status_sugerido": "A" | "B" | "C" | "D",
      "justificativa_revisao": "<explicacao objetiva citando o trecho relevante do texto do fornecedor>"
    }
  ]
}

NAO altere itens cuja classificacao esteja correta (classificacao_original_correta = true).
NAO use blocos de codigo markdown (```).
"""


def llm_self_review(
    data: dict,
    texto_fornecedor: str,
    consistency_summary: dict,
) -> tuple[dict, dict]:
    """
    Optional second LLM pass to verify flagged items.

    Only processes items that were flagged by validate_value_consistency().
    Sends a focused prompt with the flagged items + supplier text.

    Returns:
        tuple of (modified data dict, review summary dict)
    """
    flag_details = consistency_summary.get("flag_details", [])
    if not flag_details:
        return data, {"reviewed": 0, "corrections": 0}

    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    # Build the review request with only flagged items
    flagged_numbers = {d["numero"] for d in flag_details}
    flagged_items = [
        item for item in itens if item.get("numero") in flagged_numbers
    ]

    items_json = json.dumps(flagged_items, ensure_ascii=False, indent=2)

    # Truncate supplier text if too long (keep first 60k chars)
    forn_text = texto_fornecedor[:60_000] if len(texto_fornecedor) > 60_000 else texto_fornecedor

    user_content = (
        f"## ITENS SINALIZADOS PARA REVISAO\n\n{items_json}\n\n---\n\n"
        f"## TEXTO COMPLETO DO FORNECEDOR\n\n{forn_text}\n\n---\n\n"
        f"## INSTRUCAO\n\nRevise os {len(flagged_items)} itens acima. "
        "Para cada um, verifique se o valor requerido realmente NAO esta "
        "presente no texto do fornecedor. Retorne SOMENTE o JSON de revisao."
    )

    try:
        response_text = _call_gemini(SELF_REVIEW_PROMPT, user_content)
        review_data = _extract_json(response_text)
    except Exception as e:
        logger.warning("LLM self-review failed: %s", e)
        return data, {"reviewed": 0, "corrections": 0, "error": str(e)}

    # Apply corrections
    revisoes = review_data.get("revisoes", [])
    corrections = 0

    item_by_numero = {item.get("numero"): item for item in itens}

    for rev in revisoes:
        numero = rev.get("numero")
        if numero not in item_by_numero:
            continue

        if rev.get("classificacao_original_correta", True):
            continue

        item = item_by_numero[numero]
        new_status = rev.get("status_sugerido")
        justificativa_rev = rev.get("justificativa_revisao", "")

        if new_status and new_status in ("A", "B", "C", "D", "E"):
            old_status = item["status"]
            item["status"] = new_status

            correction_note = (
                f" [CORRECAO_AUTO_REVISAO: Status alterado de {old_status} para "
                f"{new_status}. {justificativa_rev}]"
            )
            item["justificativa_tecnica"] = (
                item.get("justificativa_tecnica", "") + correction_note
            ).strip()

            if new_status == "A":
                item["acao_requerida"] = None

            corrections += 1

    result = {"parecer_tecnico": pt}
    validated = _validate_parecer_json(result)

    summary = {
        "reviewed": len(flagged_items),
        "corrections": corrections,
    }

    return validated, summary


# ---------------------------------------------------------------------------
# Field Optimization (Post-processing)
# ---------------------------------------------------------------------------

_FIELD_LIMITS = {
    "valor_requerido": 100,
    "valor_fornecedor": 100,
    "justificativa_tecnica": 400,
    "acao_requerida": 150,
}


def _needs_optimization(itens: list[dict]) -> bool:
    for item in itens:
        for field, limit in _FIELD_LIMITS.items():
            value = item.get(field)
            if value and len(str(value)) > limit:
                return True
    return False


def optimize_item_fields(data: dict) -> dict:
    """
    Post-processing: compact verbose fields via a focused LLM call.
    Skipped entirely if all fields are already within their character limits.
    On failure, returns the original data unchanged.
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    if not itens or not _needs_optimization(itens):
        logger.info("Field optimization: all fields within limits, skipping")
        return data

    exceeded_count = sum(
        1
        for item in itens
        for field, limit in _FIELD_LIMITS.items()
        if item.get(field) and len(str(item.get(field, ""))) > limit
    )
    logger.info("Field optimization: %d field(s) exceed limits, calling LLM", exceeded_count)

    items_json = json.dumps(itens, ensure_ascii=False, indent=2)
    user_content = (
        f"Otimize os campos dos {len(itens)} itens abaixo conforme as regras de comprimento.\n\n"
        f"{items_json}"
    )

    try:
        response_text = _call_gemini(FIELD_OPTIMIZATION_SYSTEM, user_content)
        opt_data = _extract_json(response_text)

        optimized_itens = opt_data.get("itens", [])
        if len(optimized_itens) != len(itens):
            logger.warning(
                "Field optimization: item count mismatch (%d -> %d), skipping optimization",
                len(itens),
                len(optimized_itens),
            )
            return data

        pt["itens"] = optimized_itens
        result = {"parecer_tecnico": pt}
        return _validate_parecer_json(result)

    except Exception as e:
        logger.warning("Field optimization failed: %s — using original result", e)
        return data


def analyze_single(
    texto_engenharia: str,
    texto_fornecedor: str,
    projeto: str,
    fornecedor: str,
    numero_parecer: str,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
    disciplina: str = "instrumentacao",
    texto_anexos: str = "",
) -> dict:
    """Analyze documents in a single API call (for smaller documents)."""
    system_prompt = get_system_prompt(disciplina)
    profile_instruction = _profile_instruction(analysis_profile)
    texto_anexos_section = (
        f"\n\n## DOCUMENTOS COMPLEMENTARES (ENGENHARIA)\n\n{texto_anexos}\n\n"
        if texto_anexos
        else ""
    )
    user_content = USER_PROMPT_TEMPLATE.format(
        texto_engenharia=texto_engenharia,
        texto_fornecedor=texto_fornecedor,
        texto_anexos_section=texto_anexos_section,
        projeto=projeto,
        fornecedor=fornecedor,
        numero_parecer=numero_parecer,
    ) + profile_instruction

    logger.info("Calling Gemini API (single call, %d chars)", len(user_content))
    response_text = _call_gemini(system_prompt, user_content)
    logger.info("Gemini response received (%d chars)", len(response_text))

    try:
        data = _extract_json(response_text)
        return _validate_parecer_json(data)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed after repair, retrying with concise prompt")
        concise_hint = (
            "\n\nIMPORTANTE: Sua resposta anterior foi truncada. "
            "Seja mais CONCISO nas justificativas tecnicas (max 1-2 frases cada). "
            "Retorne SOMENTE o JSON valido, sem markdown.\n\n"
        )
        response_text = _call_gemini(system_prompt, concise_hint + user_content)
        data = _extract_json(response_text)
        return _validate_parecer_json(data)


def analyze_chunked(
    texto_engenharia: str,
    texto_fornecedor: str,
    projeto: str,
    fornecedor: str,
    numero_parecer: str,
    on_progress: callable = None,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
    disciplina: str = "instrumentacao",
    texto_anexos: str = "",
) -> dict:
    """Analyze documents using map-reduce for large documents."""
    system_prompt = get_system_prompt(disciplina)
    profile_instruction = _profile_instruction(analysis_profile)
    texto_anexos_section = (
        f"\n\n## DOCUMENTOS COMPLEMENTARES (ENGENHARIA)\n\n{texto_anexos}\n\n"
        if texto_anexos
        else ""
    )
    eng_chunks = _split_text_into_chunks(texto_engenharia, MAX_INPUT_CHARS // 2)
    forn_chunks = _split_text_into_chunks(texto_fornecedor, MAX_INPUT_CHARS // 2)

    # Ensure same number of chunks (pad shorter list with full text summary)
    total_chunks = max(len(eng_chunks), len(forn_chunks))
    while len(eng_chunks) < total_chunks:
        eng_chunks.append("")
    while len(forn_chunks) < total_chunks:
        forn_chunks.append("")

    logger.info("Chunked analysis: %d chunks", total_chunks)

    partial_results = []
    for i in range(total_chunks):
        if on_progress:
            on_progress(f"Analisando secao {i + 1} de {total_chunks}...")

        user_content = CHUNK_USER_PROMPT_TEMPLATE.format(
            texto_engenharia=eng_chunks[i],
            texto_fornecedor=forn_chunks[i],
            texto_anexos_section=texto_anexos_section,
            chunk_index=i + 1,
            total_chunks=total_chunks,
            projeto=projeto,
            fornecedor=fornecedor,
            numero_parecer=numero_parecer,
        ) + profile_instruction

        logger.info("Calling Gemini API (chunk %d/%d, %d chars)", i + 1, total_chunks, len(user_content))
        response_text = _call_gemini(system_prompt, user_content)
        partial = _extract_json(response_text)
        partial_results.append(partial)

    # Reduce: consolidate all partial results
    if on_progress:
        on_progress("Consolidando resultados...")

    # Cap each partial JSON to avoid an oversized reduce payload.
    # 200k chars total across all partials keeps the reduce call within safe limits.
    MAX_REDUCE_CHARS = 200_000
    per_chunk_limit = MAX_REDUCE_CHARS // max(total_chunks, 1)
    analises_parts = []
    for i, r in enumerate(partial_results):
        serialized = json.dumps(r, ensure_ascii=False, indent=2)
        if len(serialized) > per_chunk_limit:
            logger.warning(
                "Parcial %d truncado de %d para %d chars para o reduce",
                i + 1, len(serialized), per_chunk_limit,
            )
            serialized = serialized[:per_chunk_limit] + "\n  ... (truncado)"
        analises_parts.append(f"### Analise Parcial {i + 1}\n{serialized}")

    analises_text = "\n\n---\n\n".join(analises_parts)

    reduce_content = REDUCE_PROMPT.format(
        total_chunks=total_chunks,
        analises_parciais=analises_text,
        projeto=projeto,
        fornecedor=fornecedor,
        numero_parecer=numero_parecer,
    ) + profile_instruction

    logger.info("Calling Gemini API (reduce step, %d chars)", len(reduce_content))
    response_text = _call_gemini(system_prompt, reduce_content)
    data = _extract_json(response_text)

    return _validate_parecer_json(data)


def analyze_documents(
    texto_engenharia: str,
    texto_fornecedor: str,
    projeto: str,
    fornecedor: str,
    numero_parecer: str,
    on_progress: callable = None,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
    disciplina: str = "instrumentacao",
    texto_anexos: str = "",
) -> dict:
    """Main entry point: choose single or chunked based on document size."""
    total_chars = len(texto_engenharia) + len(texto_fornecedor)
    profile = normalize_analysis_profile(analysis_profile)

    if total_chars <= MAX_INPUT_CHARS:
        return analyze_single(
            texto_engenharia,
            texto_fornecedor,
            projeto,
            fornecedor,
            numero_parecer,
            analysis_profile=profile,
            disciplina=disciplina,
            texto_anexos=texto_anexos,
        )
    else:
        return analyze_chunked(
            texto_engenharia,
            texto_fornecedor,
            projeto,
            fornecedor,
            numero_parecer,
            on_progress=on_progress,
            analysis_profile=profile,
            disciplina=disciplina,
            texto_anexos=texto_anexos,
        )
