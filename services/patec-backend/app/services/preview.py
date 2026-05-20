import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documento import Documento
from app.models.parecer import Parecer
from app.services.analyzer import _call_gemini, _extract_json
from app.services.llm_prompt import PREVIEW_SYSTEM_PROMPT, PREVIEW_USER_PROMPT_TEMPLATE

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


def _call_preview_llm(texto_engenharia: str, parecer, feedback: str | None) -> dict:
    feedback_section = (
        f"\nFEEDBACK DO USUARIO (incorporar obrigatoriamente):\n{feedback}\n\n"
        if feedback and feedback.strip()
        else ""
    )
    user_content = PREVIEW_USER_PROMPT_TEMPLATE.format(
        texto_engenharia=texto_engenharia,
        feedback_section=feedback_section,
        projeto=parecer.projeto,
        numero_parecer=parecer.numero_parecer,
    )
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
    return await asyncio.to_thread(_call_preview_llm, texto_eng, parecer, feedback)
