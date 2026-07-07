import difflib
import json
import logging
import re
import unicodedata

from app.core.config import settings
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.seguranca import envelopar
from app.services.prompts.analise import (
    USER_PROMPT_TEMPLATE,
    CHUNK_USER_PROMPT_TEMPLATE,
    REDUCE_PROMPT,
    PROFILE_ITEM_LIMIT_TEMPLATE,
    PROFILE_INTEGRAL_TEMPLATE,
    FIELD_OPTIMIZATION_SYSTEM,
    SUPPLIER_VALUE_RECOVERY_SYSTEM,
    VERIFIER_SYSTEM,
    APPROVED_ITEMS_CONTEXT,
    get_report_language_instruction,
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


# Nomes legados: a chamada HTTP e o parsing JSON vivem em llm_client.
_call_gemini = call_llm
_extract_json = extract_json


# Canonical keys an item may carry. The analysis LLM occasionally corrupts a key
# name (e.g. "valor_fornecedor" -> "valor_necedor"), which silently drops the value
# because every reader does item.get("valor_fornecedor"). We fuzzy-match stray keys
# back onto the schema before anything reads them.
_CANONICAL_ITEM_KEYS = (
    "numero",
    "requisito_numero",
    "categoria",
    "descricao_requisito",
    "referencia_engenharia",
    "referencia_fornecedor",
    "valor_requerido",
    "valor_fornecedor",
    "status",
    "justificativa_tecnica",
    "acao_requerida",
    "prioridade",
    "norma_referencia",
)
_KEY_REPAIR_THRESHOLD = 0.75


def _is_blank(value) -> bool:
    """True for None, empty, or dash/placeholder-only supplier values."""
    if value is None:
        return True
    return str(value).strip().strip("-–—").strip().lower() in ("", "n/a", "na")


def _repair_item_keys(item: dict) -> None:
    """Remap keys the LLM corrupted (typos/truncation) back onto the canonical schema.

    Only remaps a stray key when it fuzzy-matches a canonical key above the threshold
    AND that canonical key is missing or blank — so a well-formed value is never
    clobbered. Mutates the item in place.
    """
    for key in [k for k in item if k not in _CANONICAL_ITEM_KEYS]:
        # Keys prefixed with "_" are internal pipeline annotations
        # (e.g. _verificacao_flag) — never treat them as corrupted schema keys.
        if key.startswith("_"):
            continue
        match = difflib.get_close_matches(
            key, _CANONICAL_ITEM_KEYS, n=1, cutoff=_KEY_REPAIR_THRESHOLD
        )
        if not match:
            continue
        target = match[0]
        if _is_blank(item.get(target)) and not _is_blank(item.get(key)):
            item[target] = item[key]
            item.pop(key, None)
            logger.warning("Repaired corrupted item key '%s' -> '%s'", key, target)


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
        _repair_item_keys(item)
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
            # Flag interno de QA: fica FORA da justificativa_tecnica (que e
            # exportada ao cliente) — persistido em coluna propria e exibido so
            # como badge interno na UI.
            item["_flag_consistencia"] = (
                "Termos do requisito encontrados no documento do fornecedor "
                f"({found_str}), mas o item foi classificado como {status_label}. "
                "Revisar classificacao."
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

            # Nota da correcao em coluna propria — nao suja a justificativa exportada.
            item["_nota_revisao"] = (
                f"Status alterado de {old_status} para {new_status} apos segunda "
                f"verificacao IA. {justificativa_rev}".strip()
            )

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
# Supplier Value Recovery (Post-processing)
# ---------------------------------------------------------------------------

# Statuses that imply the supplier offered something concrete for the requirement.
# An empty valor_fornecedor on these is a contradiction worth recovering.
_STATUSES_IMPLYING_OFFER = frozenset({"A", "B", "C", "E"})


def recover_missing_supplier_values(
    data: dict, texto_fornecedor: str
) -> tuple[dict, dict]:
    """Refill supplier values that came back blank for items whose status implies an
    offer (A/B/C/E). Runs AFTER the deterministic key-repair, so it only fires on
    genuine drops — not key typos. One focused LLM pass over the supplier text covers
    all flagged items at once; on failure or genuine absence, falls back to
    "Nao informado." so the table never shows a blank supplier cell.
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    flagged = [
        it
        for it in itens
        if it.get("status") in _STATUSES_IMPLYING_OFFER
        and _is_blank(it.get("valor_fornecedor"))
    ]
    summary = {
        "items_checked": len(itens),
        "items_flagged": len(flagged),
        "items_recovered": 0,
    }

    if flagged and texto_fornecedor.strip():
        try:
            payload = [
                {
                    "numero": it.get("numero"),
                    "requisito": it.get("descricao_requisito"),
                    "valor_requerido": it.get("valor_requerido"),
                }
                for it in flagged
            ]
            user_content = (
                "Recupere o valor ofertado pelo fornecedor para os itens abaixo.\n\n"
                f"ITENS:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
                f"DOCUMENTO DO FORNECEDOR:\n{texto_fornecedor}"
            )
            response_text = _call_gemini(
                SUPPLIER_VALUE_RECOVERY_SYSTEM, user_content, max_output_tokens=8192
            )
            rec = _extract_json(response_text)
            by_numero = {
                r.get("numero"): r.get("valor_fornecedor")
                for r in rec.get("itens", [])
                if isinstance(r, dict)
            }
            for it in flagged:
                novo = by_numero.get(it.get("numero"))
                if novo and not _is_blank(novo):
                    it["valor_fornecedor"] = str(novo).strip()
                    summary["items_recovered"] += 1
        except Exception as e:  # never let recovery break the pipeline
            logger.warning("Supplier value recovery failed: %s", e)

    # Deterministic guard: never persist a blank supplier cell.
    for it in itens:
        if _is_blank(it.get("valor_fornecedor")):
            it["valor_fornecedor"] = "Nao informado."

    logger.info(
        "Supplier value recovery: checked=%d flagged=%d recovered=%d",
        summary["items_checked"],
        summary["items_flagged"],
        summary["items_recovered"],
    )
    return data, summary


# ---------------------------------------------------------------------------
# Cross-item Verification (deterministic detector + stronger-model verifier)
# ---------------------------------------------------------------------------

# Supplier values that are generic and legitimately repeat across items — they
# must NOT trigger the duplicate-value flag.
_NON_DISTINCTIVE_FORN_VALUES = frozenset(
    {
        "nao informado",
        "nao informado.",
        "n/a",
        "na",
        "sim",
        "nao",
        "conforme",
        "conforme solicitado",
        "conforme requisito",
        "atende",
        "atende.",
        "atendido",
        "atendida",
        "atende ao requisito",
        "ok",
    }
)

# Below this length a supplier value is treated as too generic to be a meaningful
# duplicate (e.g. "4-20 mA", "IP-65").
_MIN_DISTINCTIVE_FORN_LEN = 8


def _supplier_value_key(value) -> str:
    """Normalized comparison key for a supplier value, or '' if not distinctive."""
    if _is_blank(value):
        return ""
    norm = _normalize_text(str(value))
    if not norm or norm in _NON_DISTINCTIVE_FORN_VALUES:
        return ""
    if len(norm) < _MIN_DISTINCTIVE_FORN_LEN:
        return ""
    return norm


def flag_items_for_verification(data: dict) -> tuple[dict, dict]:
    """Deterministic detector: marks items whose supplier value is suspect so the
    stronger verifier model re-checks only those.

    Primary signal: the SAME concrete valor_fornecedor reused across two or more
    items — typically the LLM pasting one requirement's supplier offering onto a
    sibling requirement with a different quantity/unit/TAG. Generic supplier
    values (Nao informado, Sim, Conforme...) are ignored. Sets the in-place
    annotation item['_verificacao_flag'] (cleared first so re-runs are idempotent).
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    buckets: dict[str, list[dict]] = {}
    for item in itens:
        item.pop("_verificacao_flag", None)  # idempotent re-run
        key = _supplier_value_key(item.get("valor_fornecedor"))
        if key:
            buckets.setdefault(key, []).append(item)

    flagged_numbers: list[int] = []
    for grupo in buckets.values():
        if len(grupo) < 2:
            continue
        nums = sorted(it.get("numero") for it in grupo if it.get("numero") is not None)
        for item in grupo:
            outros = [n for n in nums if n != item.get("numero")]
            if not outros:
                continue
            lista = ", ".join(str(n) for n in outros)
            item["_verificacao_flag"] = (
                f"Mesmo valor do fornecedor presente tambem no(s) item(ns) {lista} — "
                "verificar se a oferta foi atribuida a este requisito especifico "
                "(quantidade/unidade distinta?)."
            )
            if item.get("numero") is not None:
                flagged_numbers.append(item["numero"])

    summary = {
        "items_checked": len(itens),
        "items_flagged": len(flagged_numbers),
        "flagged_numbers": sorted(set(flagged_numbers)),
    }
    validated = _validate_parecer_json({"parecer_tecnico": pt})
    return validated, summary


def verify_flagged_items(
    data: dict,
    texto_engenharia: str,
    texto_fornecedor: str,
    flag_summary: dict,
) -> tuple[dict, dict]:
    """Stronger-model (Pro) pass over the items flagged by the deterministic
    detector. Reads the requirement + the engineering/supplier text and decides,
    per item, whether the supplier value was attributed correctly.

    Propose-with-trace: every reviewed item gets a '_verificacao_nota' (confirming
    or correcting); corrections also rewrite status/value/justificativa. Failures
    never break the pipeline — the original data is returned unchanged.
    """
    flagged_numbers = set(flag_summary.get("flagged_numbers", []))
    if not flagged_numbers:
        return data, {"reviewed": 0, "corrections": 0}

    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])
    item_by_numero = {it.get("numero"): it for it in itens}
    flagged_items = [it for it in itens if it.get("numero") in flagged_numbers]

    payload = [
        {
            "numero": it.get("numero"),
            "requisito": it.get("descricao_requisito"),
            "valor_requerido": it.get("valor_requerido"),
            "referencia_engenharia": it.get("referencia_engenharia"),
            "status_atual": it.get("status"),
            "valor_fornecedor_atual": it.get("valor_fornecedor"),
            "justificativa_atual": it.get("justificativa_tecnica"),
            "motivo_flag": it.get("_verificacao_flag"),
        }
        for it in flagged_items
    ]

    eng_text = texto_engenharia[:60_000]
    forn_text = texto_fornecedor[:60_000]
    user_content = (
        "## ITENS SINALIZADOS PARA VERIFICACAO\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n---\n\n"
        f"## TEXTO DA ENGENHARIA\n\n{eng_text}\n\n---\n\n"
        f"## TEXTO DO FORNECEDOR\n\n{forn_text}\n\n---\n\n"
        f"## INSTRUCAO\n\nVerifique os {len(flagged_items)} itens acima conforme as "
        "regras. Retorne SOMENTE o JSON de verificacao."
    )

    try:
        response_text = _call_gemini(
            VERIFIER_SYSTEM,
            user_content,
            model=settings.GEMINI_VERIFIER_MODEL,
            max_output_tokens=16384,
        )
        review = _extract_json(response_text)
    except Exception as e:  # never let verification break the pipeline
        logger.warning("LLM verifier failed: %s", e)
        return data, {"reviewed": len(flagged_items), "corrections": 0, "error": str(e)}

    corrections = 0
    for rev in review.get("itens", []):
        if not isinstance(rev, dict):
            continue
        item = item_by_numero.get(rev.get("numero"))
        if item is None:
            continue
        nota = (rev.get("nota") or "").strip()

        if rev.get("correto", True):
            item["_verificacao_nota"] = (
                f"Verificado (IA Pro): {nota}"
                if nota
                else "Verificado (IA Pro): atribuicao confirmada."
            )
            continue

        novo_valor = rev.get("valor_fornecedor_corrigido")
        if novo_valor and not _is_blank(novo_valor):
            item["valor_fornecedor"] = str(novo_valor).strip()
        novo_status = rev.get("status_corrigido")
        if novo_status in ("A", "B", "C", "D", "E"):
            item["status"] = novo_status
        nova_justif = (rev.get("justificativa_corrigida") or "").strip()
        if nova_justif:
            item["justificativa_tecnica"] = nova_justif
        nova_acao = rev.get("acao_requerida_corrigida")
        if nova_acao is not None:
            item["acao_requerida"] = (str(nova_acao).strip() or None)
        item["_verificacao_nota"] = (
            f"Corrigido pela verificacao (IA Pro): {nota}"
            if nota
            else "Corrigido pela verificacao (IA Pro)."
        )
        corrections += 1

    validated = _validate_parecer_json({"parecer_tecnico": pt})
    return validated, {"reviewed": len(flagged_items), "corrections": corrections}


# ---------------------------------------------------------------------------
# Field Optimization (Post-processing)
# ---------------------------------------------------------------------------

_FIELD_LIMITS = {
    "valor_requerido": 100,
    "valor_fornecedor": 100,
    "justificativa_tecnica": 400,
    "acao_requerida": 150,
}

# Únicos campos que a otimização reescreve — o resto do item é preservado intacto.
_OPTIMIZABLE_FIELDS = frozenset(_FIELD_LIMITS)


def _needs_optimization(itens: list[dict]) -> bool:
    for item in itens:
        for field, limit in _FIELD_LIMITS.items():
            value = item.get(field)
            if value and len(str(value)) > limit:
                return True
    return False


def optimize_item_fields(data: dict, idioma_relatorio: str = "pt") -> dict:
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
    ) + get_report_language_instruction(idioma_relatorio)

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

        # Merge: a otimização SÓ reescreve os 4 campos de texto longos; todos os
        # demais campos vêm do item original (preserva requisito_numero, status,
        # numero etc. — senão a LLM os derruba e o vínculo item↔requisito quebra).
        merged = []
        for original, opt in zip(itens, optimized_itens):
            novo = dict(original)
            for campo in _OPTIMIZABLE_FIELDS:
                if campo in opt:
                    novo[campo] = opt[campo]
            merged.append(novo)

        pt["itens"] = merged
        result = {"parecer_tecnico": pt}
        return _validate_parecer_json(result)

    except Exception as e:
        logger.warning("Field optimization failed: %s — using original result", e)
        return data


# ---------------------------------------------------------------------------
# Reconciliação de Escopo Fechado (Post-processing)
# ---------------------------------------------------------------------------

def reconciliar_escopo_fechado(
    data: dict, requisitos_payload: list[dict]
) -> tuple[dict, dict]:
    """Garante que a análise cobre EXATAMENTE os requisitos aprovados (escopo fechado).

    O contrato do escopo fechado (1 item por requisito aprovado) era confiado à
    LLM sem verificação: se o modelo devolvia menos itens (truncamento, confusão,
    recusa/injeção), o parecer era salvo cobrindo menos do que o engenheiro
    aprovou — em silêncio. Aqui, para cada requisito aprovado SEM item vinculado
    (por `requisito_numero`), injetamos um placeholder status D; requisitos com
    mais de um item são sinalizados como duplicados. Itens adicionais do
    fornecedor (status E, `requisito_numero` nulo) são ignorados. Roda no
    pipeline pós-cache — NÃO exige bump de PROMPT_VERSION.
    """
    pt = data.get("parecer_tecnico", data)
    itens = pt.get("itens", [])

    itens_por_req: dict[int, list[dict]] = {}
    for it in itens:
        numero = it.get("requisito_numero")
        if isinstance(numero, int):
            itens_por_req.setdefault(numero, []).append(it)

    faltantes: list[int] = []
    duplicados: list[int] = []
    for r in requisitos_payload:
        numero = r.get("numero")
        grupo = itens_por_req.get(numero, [])
        if not grupo:
            faltantes.append(numero)
            itens.append({
                "requisito_numero": numero,
                "numero": 0,  # renumerado por _validate_parecer_json
                "categoria": r.get("categoria"),
                "descricao_requisito": r.get("descricao_requisito", ""),
                "referencia_engenharia": r.get("referencia_engenharia"),
                "referencia_fornecedor": "Nao encontrado",
                "valor_requerido": r.get("valor_requerido"),
                "valor_fornecedor": "Nao informado.",
                "status": "D",
                "justificativa_tecnica": (
                    "Requisito aprovado nao coberto pela analise automatica "
                    "(possivel truncamento ou omissao do modelo). Revisar "
                    "manualmente este item."
                ),
                "acao_requerida": (
                    "Analisar manualmente este requisito contra a proposta do fornecedor."
                ),
                "prioridade": r.get("prioridade") or "MEDIA",
                "norma_referencia": r.get("norma_referencia"),
            })
        elif len(grupo) > 1:
            duplicados.append(numero)

    summary = {
        "requisitos_aprovados": len(requisitos_payload),
        "itens_faltantes": len(faltantes),
        "numeros_faltantes": sorted(faltantes),
        "requisitos_duplicados": sorted(duplicados),
    }
    if faltantes or duplicados:
        logger.warning(
            "Reconciliacao de escopo: %d requisito(s) sem item (%s); duplicados=%s",
            len(faltantes), sorted(faltantes), sorted(duplicados),
        )
    validated = _validate_parecer_json({"parecer_tecnico": pt})
    return validated, summary


def analyze_single(
    texto_engenharia: str,
    texto_fornecedor: str,
    projeto: str,
    fornecedor: str,
    numero_parecer: str,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
    disciplina: str = "instrumentacao",
    idioma_relatorio: str = "pt",
    texto_anexos: str = "",
    itens_aprovados: list[dict] | None = None,
) -> dict:
    """Analyze documents in a single API call (for smaller documents)."""
    system_prompt = get_system_prompt(disciplina)
    # When itens_aprovados is set, the user already decided the scope — skip profile limit
    # to avoid the LLM discarding approved items that exceed the profile's max count.
    profile_instruction = "" if itens_aprovados else _profile_instruction(analysis_profile)
    texto_anexos_section = (
        "\n\n## DOCUMENTOS COMPLEMENTARES (ENGENHARIA)\n"
        + envelopar("DOC_ANEXOS_ENGENHARIA", texto_anexos)
        + "\n\n"
        if texto_anexos
        else ""
    )
    approved_section = (
        APPROVED_ITEMS_CONTEXT.format(
            itens_json=json.dumps(itens_aprovados, ensure_ascii=False, indent=2),
            total=len(itens_aprovados),
        )
        if itens_aprovados
        else ""
    )
    user_content = USER_PROMPT_TEMPLATE.format(
        texto_engenharia=texto_engenharia,
        texto_fornecedor=texto_fornecedor,
        texto_anexos_section=texto_anexos_section,
        projeto=projeto,
        fornecedor=fornecedor,
        numero_parecer=numero_parecer,
    ) + approved_section + profile_instruction + get_report_language_instruction(idioma_relatorio)

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
    idioma_relatorio: str = "pt",
    texto_anexos: str = "",
    itens_aprovados: list[dict] | None = None,
) -> dict:
    """Analyze documents using map-reduce for large documents."""
    system_prompt = get_system_prompt(disciplina)
    # When itens_aprovados is set, the user already decided the scope — skip profile limit
    profile_instruction = "" if itens_aprovados else _profile_instruction(analysis_profile)
    texto_anexos_section = (
        "\n\n## DOCUMENTOS COMPLEMENTARES (ENGENHARIA)\n"
        + envelopar("DOC_ANEXOS_ENGENHARIA", texto_anexos)
        + "\n\n"
        if texto_anexos
        else ""
    )
    approved_section = (
        APPROVED_ITEMS_CONTEXT.format(
            itens_json=json.dumps(itens_aprovados, ensure_ascii=False, indent=2),
            total=len(itens_aprovados),
        )
        if itens_aprovados
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
        ) + approved_section + profile_instruction + get_report_language_instruction(idioma_relatorio)

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
    ) + profile_instruction + get_report_language_instruction(idioma_relatorio)

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
    idioma_relatorio: str = "pt",
    texto_anexos: str = "",
    itens_aprovados: list[dict] | None = None,
) -> dict:
    """Main entry point: choose single or chunked based on document size."""
    total_chars = len(texto_engenharia) + len(texto_fornecedor)
    profile = normalize_analysis_profile(analysis_profile)

    # Escopo fechado (requisitos aprovados): SEMPRE chamada única. O caminho
    # chunked gera um conjunto de itens por chunk e o reduce os concatena —
    # com escopo fechado isso DUPLICA os itens (N chunks ≈ N× os requisitos).
    # A chamada única produz exatamente 1 item por requisito aprovado; o contexto
    # do Gemini comporta o documento inteiro com folga.
    if itens_aprovados or total_chars <= MAX_INPUT_CHARS:
        return analyze_single(
            texto_engenharia,
            texto_fornecedor,
            projeto,
            fornecedor,
            numero_parecer,
            analysis_profile=profile,
            disciplina=disciplina,
            idioma_relatorio=idioma_relatorio,
            texto_anexos=texto_anexos,
            itens_aprovados=itens_aprovados,
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
            idioma_relatorio=idioma_relatorio,
            texto_anexos=texto_anexos,
            itens_aprovados=itens_aprovados,
        )
