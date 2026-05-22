import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documento import Documento
from app.models.parecer import Parecer
from app.services.analyzer import _call_gemini, _extract_json
from app.services.llm_prompt import (
    PREVIEW_SYSTEM_PROMPT,
    PREVIEW_USER_PROMPT_TEMPLATE,
)
from app.services.analyzer import get_profile_label, get_profile_max_itens, normalize_analysis_profile

logger = logging.getLogger(__name__)


async def _load_eng_text(parecer_id, db: AsyncSession):
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise ValueError("Parecer nao encontrado.")

    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = docs_result.scalars().all()
    eng_docs = [d for d in docs if d.tipo == "engenharia"]

    if not eng_docs:
        raise ValueError(
            "Faca upload de pelo menos um documento de engenharia antes de gerar o preview."
        )

    texto = "\n\n---\n\n".join(
        f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}" for d in eng_docs
    )
    return texto, parecer


def _call_preview_llm(texto_engenharia: str, parecer, perfil_analise: str, feedback: str | None) -> dict:
    feedback_section = (
        f"\nFEEDBACK DO USUARIO (incorporar obrigatoriamente):\n{feedback}\n\n"
        if feedback and feedback.strip()
        else ""
    )
    normalized_profile = normalize_analysis_profile(perfil_analise)
    max_itens = get_profile_max_itens(normalized_profile)
    profile_label = get_profile_label(normalized_profile)
    # When the user provides feedback they are explicitly redefining scope,
    # so the profile item-count limit must not apply.
    limit_instruction = (
        ""
        if feedback and feedback.strip()
        else (
            f"\n\nRESTRICAO DE VOLUME: retorne NO MAXIMO {max_itens} itens "
            f"(perfil {profile_label}). Priorize seguranca, certificacoes e desvios criticos.\n"
        )
    )
    user_content = PREVIEW_USER_PROMPT_TEMPLATE.format(
        texto_engenharia=texto_engenharia,
        feedback_section=feedback_section,
        projeto=parecer.projeto,
        numero_parecer=parecer.numero_parecer,
    ) + limit_instruction
    logger.info(
        "Preview LLM call: parecer=%s, eng_chars=%d, has_feedback=%s",
        parecer.id,
        len(texto_engenharia),
        bool(feedback),
    )
    response_text = _call_gemini(PREVIEW_SYSTEM_PROMPT, user_content)
    data = _extract_json(response_text)

    itens = data.get("itens_candidatos", [])
    valid_prios = {"ALTA", "MEDIA", "BAIXA"}
    for i, item in enumerate(itens):
        item["numero"] = i + 1
        if item.get("prioridade") not in valid_prios:
            item["prioridade"] = "MEDIA"
        item.setdefault(
            "descricao_requisito",
            item.get("description", item.get("descricao", item.get("requirement_description", ""))),
        )
        item.setdefault("norma_referencia", None)
        item.setdefault("referencia_engenharia", "")

    return {
        "itens_candidatos": itens,
        "total_itens": len(itens),
        "resumo": data.get("resumo", ""),
    }


async def gerar_preview_itens(
    parecer_id,
    db: AsyncSession,
    perfil_analise: str,
    feedback: str | None = None,
) -> dict:
    texto_eng, parecer = await _load_eng_text(parecer_id, db)
    return await asyncio.to_thread(_call_preview_llm, texto_eng, parecer, perfil_analise, feedback)
