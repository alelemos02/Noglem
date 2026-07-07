"""
Extracao e aprovacao de requisitos de engenharia (blocos 8-10 do fluxo, operacao W1).

A LLM extrai a lista candidata APENAS dos documentos de engenharia. A lista
extraida e persistida imediatamente como RASCUNHO (`aprovado_em IS NULL`) —
visivel e editavel pelo engenheiro (tela ou chat JULIA), sobrevivendo a
recargas. So na aprovacao (W1) os registros ganham `aprovado_em` e viram a
fonte unica de verdade. A analise (R1) le exclusivamente os aprovados.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.documento import Documento
from app.models.parecer import Parecer
from app.models.requisito import Requisito
from app.models.usuario import Usuario
from app.services.analyzer import (
    get_profile_label,
    get_profile_max_itens,
    normalize_analysis_profile,
)
from app.services.doc_selection import eng_docs_correntes
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.extracao import (
    EXTRACAO_SYSTEM_PROMPT,
    EXTRACAO_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Fases em que a lista de requisitos ainda pode ser (re)aprovada — antes de a
# analise inicial rodar, a lista e substituivel; depois, so via revisao de spec (W7).
_FASES_APROVACAO = {"SETUP", "REQUISITOS", "ANALISE"}


async def _load_parecer(parecer_id, db: AsyncSession) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise ValueError("Parecer nao encontrado.")
    return parecer


async def _load_eng_text(parecer_id, db: AsyncSession) -> str:
    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = docs_result.scalars().all()
    # Só a revisão mais recente de cada arquivo (evita duplicar revisões de spec)
    eng_docs = eng_docs_correntes(list(docs))

    if not eng_docs:
        raise ValueError(
            "Faca upload de pelo menos um documento de engenharia antes de extrair requisitos."
        )

    return "\n\n---\n\n".join(
        f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}" for d in eng_docs
    )


def _call_extracao_llm(
    texto_engenharia: str, parecer: Parecer, perfil_analise: str, feedback: str | None
) -> dict:
    feedback_section = (
        f"\nFEEDBACK DO USUARIO (incorporar obrigatoriamente):\n{feedback}\n\n"
        if feedback and feedback.strip()
        else ""
    )
    normalized_profile = normalize_analysis_profile(perfil_analise)
    max_itens = get_profile_max_itens(normalized_profile)
    profile_label = get_profile_label(normalized_profile)
    # O teto de itens do perfil continua valendo MESMO com feedback. Feedback que
    # RESTRINGE o escopo ("so o capitulo 2") deve diminuir a lista, nunca explodi-la
    # — so liberamos o teto quando o usuario pede explicitamente a lista inteira (ou
    # no perfil integral). Sem isso, um recorte mal interpretado virava 90+ itens.
    fb = (feedback or "").strip().lower()
    quer_tudo = normalized_profile == "integral" or any(
        termo in fb
        for termo in (
            "todos",
            "todas as",
            "tudo",
            "integral",
            "sem limite",
            "lista completa",
            "lista inteira",
            "documento inteiro",
        )
    )
    limit_instruction = (
        ""
        if quer_tudo
        else (
            f"\n\nRESTRICAO DE VOLUME: retorne NO MAXIMO {max_itens} requisitos "
            f"(perfil {profile_label}). Priorize seguranca, certificacoes e desvios criticos.\n"
        )
    )
    user_content = EXTRACAO_USER_PROMPT_TEMPLATE.format(
        texto_engenharia=texto_engenharia,
        feedback_section=feedback_section,
        projeto=parecer.projeto,
        numero_parecer=parecer.numero_parecer,
    ) + limit_instruction

    logger.info(
        "Extracao de requisitos via LLM: parecer=%s, modelo=%s, eng_chars=%d, "
        "quer_tudo=%s, has_feedback=%s, escopo=%r",
        parecer.id,
        settings.GEMINI_EXTRACTION_MODEL,
        len(texto_engenharia),
        quer_tudo,
        bool(feedback),
        (feedback or "")[:140],
    )
    response_text = call_llm(
        EXTRACAO_SYSTEM_PROMPT,
        user_content,
        model=settings.GEMINI_EXTRACTION_MODEL,
    )
    data = extract_json(response_text)

    requisitos = data.get("requisitos", data.get("itens_candidatos", []))
    valid_prios = {"ALTA", "MEDIA", "BAIXA"}
    for i, item in enumerate(requisitos):
        item["numero"] = i + 1
        if item.get("prioridade") not in valid_prios:
            item["prioridade"] = "MEDIA"
        item.setdefault(
            "descricao_requisito",
            item.get("description", item.get("descricao", "")),
        )
        item.setdefault("valor_requerido", None)
        item.setdefault("norma_referencia", None)
        item.setdefault("referencia_engenharia", "")
        item.setdefault("categoria", None)

    return {
        "requisitos": requisitos,
        "total_itens": len(requisitos),
        "resumo": data.get("resumo", ""),
    }


async def _checar_pre_analise(parecer: Parecer, db: AsyncSession) -> None:
    """Edicao de requisitos so vale ate a fase ANALISE (antes do ciclo).

    Em SETUP/REQUISITOS/ANALISE a lista pode ser editada e (re)aprovada — mesmo
    que ja existam itens da analise inicial, pois reaprovar redispara o R1 e os
    itens sao regenerados do zero (nao ha historico de ciclo a orfaozar). A
    partir de CICLO_FORNECEDOR as mudancas passam pela revisao de especificacao
    (W7), que preserva o historico append-only por item.
    """
    if parecer.fase_caso not in _FASES_APROVACAO:
        raise ValueError(
            f"Operacao indisponivel na fase {parecer.fase_caso}. "
            "Apos o inicio do ciclo, use a revisao de especificacao."
        )


async def salvar_draft(
    parecer_id,
    db: AsyncSession,
    itens: list[dict],
) -> list[Requisito]:
    """Substitui o rascunho de requisitos (aprovado_em IS NULL) no BD.

    Chamado pela extracao, pela edicao manual na tela e pelas acoes da JULIA
    via chat. Os aprovados (W1) nao sao tocados aqui.
    """
    parecer = await _load_parecer(parecer_id, db)
    await _checar_pre_analise(parecer, db)

    await db.execute(
        delete(Requisito).where(
            Requisito.parecer_id == parecer_id,
            Requisito.aprovado_em.is_(None),
        )
    )

    requisitos: list[Requisito] = []
    valid_prios = {"ALTA", "MEDIA", "BAIXA"}
    for i, item in enumerate(itens):
        descricao = (item.get("descricao_requisito") or "").strip()
        if not descricao:
            continue
        prioridade = item.get("prioridade")
        requisito = Requisito(
            parecer_id=parecer.id,
            numero=i + 1,
            categoria=item.get("categoria"),
            descricao_requisito=descricao,
            referencia_engenharia=item.get("referencia_engenharia"),
            valor_requerido=item.get("valor_requerido"),
            prioridade=prioridade if prioridade in valid_prios else "MEDIA",
            norma_referencia=item.get("norma_referencia"),
            aprovado_por=None,
            aprovado_em=None,
        )
        db.add(requisito)
        requisitos.append(requisito)

    await db.commit()
    for r in requisitos:
        await db.refresh(r)
    logger.info(
        "Draft de requisitos salvo: %d itens (parecer %s)",
        len(requisitos),
        parecer_id,
    )
    return requisitos


async def listar_draft(parecer_id, db: AsyncSession) -> list[Requisito]:
    await _load_parecer(parecer_id, db)
    result = await db.execute(
        select(Requisito)
        .where(
            Requisito.parecer_id == parecer_id,
            Requisito.aprovado_em.is_(None),
        )
        .order_by(Requisito.numero)
    )
    return list(result.scalars().all())


async def extrair_requisitos(
    parecer_id,
    db: AsyncSession,
    perfil_analise: str,
    feedback: str | None = None,
) -> dict:
    """Extrai a lista candidata de requisitos (blocos 8-9) e persiste como rascunho."""
    parecer = await _load_parecer(parecer_id, db)
    if parecer.fase_caso not in _FASES_APROVACAO:
        raise ValueError(
            f"Extracao de requisitos indisponivel na fase {parecer.fase_caso}. "
            "Apos a analise, use a revisao de especificacao."
        )

    texto_eng = await _load_eng_text(parecer_id, db)
    data = await asyncio.to_thread(
        _call_extracao_llm, texto_eng, parecer, perfil_analise, feedback
    )

    if parecer.fase_caso == "SETUP":
        parecer.fase_caso = "REQUISITOS"
        await db.commit()

    # Persiste o rascunho: sobrevive a recargas e fica visivel na tabela do caso
    await salvar_draft(parecer_id, db, data["requisitos"])

    return data


async def aprovar_requisitos(
    parecer_id,
    db: AsyncSession,
    itens: list[dict],
    usuario: Usuario | None,
) -> tuple[Parecer, list[Requisito]]:
    """
    Operacao W1: persiste a lista de requisitos validada pelo engenheiro e
    avanca o caso para a fase ANALISE.

    Ate a fase ANALISE, reaprovar substitui a lista anterior (a reanalise
    regenera os itens). A partir do ciclo com o fornecedor, a lista e imutavel
    por aqui — alteracoes passam pela revisao de especificacao (W7).
    """
    parecer = await _load_parecer(parecer_id, db)

    if parecer.fase_caso not in _FASES_APROVACAO:
        raise ValueError(
            f"Aprovacao de requisitos indisponivel na fase {parecer.fase_caso}. "
            "Apos o inicio do ciclo, use a revisao de especificacao."
        )

    # Substitui lista anterior (permitido apenas pre-analise; nada referencia esses registros)
    await db.execute(delete(Requisito).where(Requisito.parecer_id == parecer_id))

    agora = datetime.utcnow()
    requisitos: list[Requisito] = []
    for i, item in enumerate(itens):
        requisito = Requisito(
            parecer_id=parecer.id,
            numero=i + 1,
            categoria=item.get("categoria"),
            descricao_requisito=item["descricao_requisito"],
            referencia_engenharia=item.get("referencia_engenharia"),
            valor_requerido=item.get("valor_requerido"),
            prioridade=item.get("prioridade") or "MEDIA",
            norma_referencia=item.get("norma_referencia"),
            aprovado_por=usuario.id if usuario else None,
            aprovado_em=agora,
        )
        db.add(requisito)
        requisitos.append(requisito)

    parecer.fase_caso = "ANALISE"
    await db.commit()
    for r in requisitos:
        await db.refresh(r)
    await db.refresh(parecer)

    logger.info(
        "W1: %d requisitos aprovados para parecer %s (fase_caso=ANALISE)",
        len(requisitos),
        parecer_id,
    )
    return parecer, requisitos


async def reabrir_requisitos(parecer_id, db: AsyncSession) -> list[Requisito]:
    """Reabre a lista de requisitos aprovados para edicao (fase ANALISE).

    Copia os requisitos aprovados de volta para um RASCUNHO editavel (mesma
    máquina do W1): o engenheiro revê/edita a lista sem a comparação do
    fornecedor e, ao aprovar, a análise é refeita com a nova lista. Os itens da
    análise atual permanecem intactos até a reaprovação. Indisponível a partir
    do ciclo com o fornecedor (use a revisão de especificação).
    """
    parecer = await _load_parecer(parecer_id, db)
    if parecer.fase_caso not in _FASES_APROVACAO:
        raise ValueError(
            f"Edicao de requisitos indisponivel na fase {parecer.fase_caso}. "
            "Apos o inicio do ciclo, use a revisao de especificacao."
        )

    aprovados = await listar_requisitos(parecer_id, db)
    if not aprovados:
        raise ValueError("Nao ha requisitos aprovados para reabrir.")

    itens = [
        {
            "categoria": r.categoria,
            "descricao_requisito": r.descricao_requisito,
            "referencia_engenharia": r.referencia_engenharia,
            "valor_requerido": r.valor_requerido,
            "prioridade": r.prioridade,
            "norma_referencia": r.norma_referencia,
        }
        for r in aprovados
    ]
    draft = await salvar_draft(parecer_id, db, itens)
    logger.info(
        "Requisitos reabertos para edicao: %d itens (parecer %s)",
        len(draft),
        parecer_id,
    )
    return draft


async def listar_requisitos(parecer_id, db: AsyncSession) -> list[Requisito]:
    """Lista os requisitos APROVADOS (W1) — rascunhos ficam em listar_draft."""
    await _load_parecer(parecer_id, db)
    result = await db.execute(
        select(Requisito)
        .where(
            Requisito.parecer_id == parecer_id,
            Requisito.aprovado_em.isnot(None),
        )
        .order_by(Requisito.numero)
    )
    return list(result.scalars().all())


async def atualizar_requisito(
    parecer_id,
    requisito_id,
    db: AsyncSession,
    campos: dict,
) -> Requisito:
    """Edita um requisito — permitido ate a fase ANALISE (antes do ciclo)."""
    parecer = await _load_parecer(parecer_id, db)
    if parecer.fase_caso not in _FASES_APROVACAO:
        raise ValueError(
            f"Edicao de requisitos indisponivel na fase {parecer.fase_caso}. "
            "Apos o inicio do ciclo, use a revisao de especificacao."
        )

    result = await db.execute(
        select(Requisito).where(
            Requisito.id == requisito_id, Requisito.parecer_id == parecer_id
        )
    )
    requisito = result.scalar_one_or_none()
    if not requisito:
        raise ValueError("Requisito nao encontrado.")

    for campo, valor in campos.items():
        if valor is not None:
            setattr(requisito, campo, valor)

    await db.commit()
    await db.refresh(requisito)
    return requisito
