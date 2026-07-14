"""
Extracao e aprovacao de requisitos de engenharia (blocos 8-10 do fluxo, operacao W1).

A LLM extrai a lista candidata APENAS dos documentos de engenharia. A lista
extraida e persistida imediatamente como RASCUNHO (`aprovado_em IS NULL`) —
visivel e editavel pelo engenheiro (tela ou chat JULIA), sobrevivendo a
recargas. So na aprovacao (W1) os registros ganham `aprovado_em` e viram a
fonte unica de verdade. A analise (R1) le exclusivamente os aprovados.
"""

import asyncio
import json
import logging
import re
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.documento import Documento
from app.models.parecer import Parecer
from app.models.requisito import Requisito
from app.models.usuario import Usuario
from app.services.analyzer import (
    _normalize_text,
    get_profile_label,
    get_profile_max_itens,
    normalize_analysis_profile,
)
from app.services.doc_selection import anexo_docs_correntes, eng_docs_correntes
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.extracao import (
    AMARRACAO_SYSTEM_PROMPT,
    AMARRACAO_USER_PROMPT_TEMPLATE,
    EXTRACAO_SYSTEM_PROMPT,
    EXTRACAO_USER_PROMPT_TEMPLATE,
)
from app.services.prompts.seguranca import envelopar

logger = logging.getLogger(__name__)

# Fases em que a lista de requisitos ainda pode ser (re)aprovada — antes de a
# analise inicial rodar, a lista e substituivel; depois, so via revisao de spec (W7).
_FASES_APROVACAO = {"SETUP", "REQUISITOS", "ANALISE"}

# Passe de amarracoes (ajuste #12): requisitos que remetem a documentos ANEXOS
# ("Sistema CFTV conforme TK-8") sao decompostos no desdobramento real do anexo.
_ANEXO_TEXT_SLICE = 120_000   # chars por anexo (a tabela-alvo pode estar funda)
_ANEXOS_MAX_TOTAL = 300_000   # acima disso o passe e pulado (request sincrono)
_ANEXO_MIN_CHARS = 200        # abaixo disso o texto e ilegivel (OCR vazio)
_MAX_SUBS_POR_ITEM = 80       # sanity cap por requisito decomposto
_PRIORIDADES_VALIDAS = {"ALTA", "MEDIA", "BAIXA"}
_REF_KEYWORDS = (
    "conforme", "especificacao", "criterio de projeto", "anexo",
    "vide", "ver documento", "atende a", "de acordo com",
)


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
            f"(perfil {profile_label}). Priorize seguranca, certificacoes e desvios criticos. "
            "Itens amarrados a documentos anexos serao desdobrados num passe seguinte e NAO "
            "contam neste limite — mantenha cada um como UM item com a referencia explicita.\n"
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


async def _load_anexos_texto(
    parecer_id, db: AsyncSession
) -> tuple[list[tuple[str, str]], list[str]]:
    """Anexos da engenharia legiveis [(nome, texto ate _ANEXO_TEXT_SLICE)] e a
    lista de nomes ilegiveis (texto ausente/curto demais — upload sem OCR util)."""
    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = docs_result.scalars().all()
    legiveis: list[tuple[str, str]] = []
    ilegiveis: list[str] = []
    for d in anexo_docs_correntes(list(docs)):
        texto = (d.texto_extraido or "").strip()
        if len(texto) < _ANEXO_MIN_CHARS:
            ilegiveis.append(d.nome_arquivo)
        else:
            legiveis.append((d.nome_arquivo, texto[:_ANEXO_TEXT_SLICE]))
    return legiveis, ilegiveis


def _anexos_citados(
    requisitos: list[dict], anexos: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Pre-filtro deterministico (zero LLM) do passe de amarracoes.

    Um anexo e candidato quando algum stem do nome do arquivo (tokens
    alfanumericos len>=3 do nome sem extensao, incluindo pares adjacentes e o
    nome colado: "TK-8" vira "tk8") aparece no texto dos requisitos. Sem stem
    citado mas com palavra-chave generica de referencia em algum requisito,
    todos os anexos entram (o LLM decide). Sem nada: passe pulado. Falso
    positivo aqui e barato — so inclui o anexo na chamada batched.
    """
    texto_reqs = _normalize_text(
        " | ".join(
            " ".join(
                str(r.get(campo) or "")
                for campo in (
                    "descricao_requisito",
                    "valor_requerido",
                    "referencia_engenharia",
                    "norma_referencia",
                )
            )
            for r in requisitos
        )
    )
    texto_reqs_colado = re.sub(r"[^a-z0-9]+", "", texto_reqs)

    citados: list[tuple[str, str]] = []
    for nome, texto in anexos:
        base = _normalize_text(nome.rsplit(".", 1)[0])
        partes = [p for p in re.split(r"[^a-z0-9]+", base) if p]
        stems = {p for p in partes if len(p) >= 3}
        stems.update(
            a + b for a, b in zip(partes, partes[1:]) if len(a + b) >= 3
        )
        if any(s in texto_reqs or s in texto_reqs_colado for s in stems):
            citados.append((nome, texto))

    if not citados and any(k in texto_reqs for k in _REF_KEYWORDS):
        return list(anexos)
    return citados


def _merge_decomposicoes(
    base: list[dict], decomposicoes: list[dict], cap: int = _MAX_SUBS_POR_ITEM
) -> list[dict]:
    """Substitui cada requisito decomposto pelos seus sub-requisitos NA POSICAO,
    renumerando 1..N; os demais ficam intactos. Funcao pura (testavel).

    Guardas: numero_original inexistente e ignorado; decomposicao sem subs
    validos ou acima do cap mantem o requisito original; sub sem descricao e
    descartado; decomposicao duplicada para o mesmo numero — a primeira vence;
    categoria/prioridade ausentes herdam do requisito original.
    """
    por_numero: dict[int, list[dict]] = {}
    for dec in decomposicoes or []:
        if not isinstance(dec, dict):
            continue
        numero = dec.get("numero_original")
        if not isinstance(numero, int) or isinstance(numero, bool):
            continue
        if numero in por_numero:
            logger.warning(
                "Decomposicao duplicada para o requisito %s — primeira vence", numero
            )
            continue
        subs_validos = [
            s
            for s in (dec.get("sub_requisitos") or [])
            if isinstance(s, dict) and str(s.get("descricao_requisito") or "").strip()
        ]
        if not subs_validos or len(subs_validos) > cap:
            logger.warning(
                "Decomposicao do requisito %s descartada (%d subs validos; cap=%d)",
                numero,
                len(subs_validos),
                cap,
            )
            continue
        por_numero[numero] = subs_validos

    if not por_numero:
        return base

    resultado: list[dict] = []
    for item in base:
        subs = por_numero.get(item.get("numero"))
        if subs is None:
            resultado.append(item)
            continue
        for s in subs:
            prioridade = s.get("prioridade")
            if prioridade not in _PRIORIDADES_VALIDAS:
                prioridade = item.get("prioridade") or "MEDIA"
            resultado.append(
                {
                    "categoria": s.get("categoria") or item.get("categoria"),
                    "descricao_requisito": str(s.get("descricao_requisito")).strip(),
                    "valor_requerido": s.get("valor_requerido"),
                    "prioridade": prioridade,
                    "norma_referencia": s.get("norma_referencia"),
                    "referencia_engenharia": s.get("referencia_engenharia")
                    or item.get("referencia_engenharia")
                    or "",
                }
            )
    for i, item in enumerate(resultado):
        item["numero"] = i + 1
    return resultado


def _resolver_amarracoes_sync(
    data: dict, anexos: list[tuple[str, str]], parecer: Parecer
) -> dict:
    """Passe 2 da extracao (ajuste #12): UMA chamada batched que decompoe os
    requisitos amarrados a anexos no desdobramento real do documento.

    Qualquer falha (LLM, JSON invalido) devolve `data` intacto — o passe nunca
    deixa a extracao pior do que era sem ele.
    """
    try:
        requisitos_base = data.get("requisitos") or []
        requisitos_json = json.dumps(
            [
                {
                    campo: r.get(campo)
                    for campo in (
                        "numero",
                        "categoria",
                        "descricao_requisito",
                        "valor_requerido",
                        "prioridade",
                        "norma_referencia",
                        "referencia_engenharia",
                    )
                }
                for r in requisitos_base
            ],
            ensure_ascii=False,
        )
        anexos_secao = "\n\n".join(
            f"### ANEXO: {nome}\n" + envelopar("DOC_ANEXO_ENGENHARIA", texto)
            for nome, texto in anexos
        )
        user_content = AMARRACAO_USER_PROMPT_TEMPLATE.format(
            requisitos_json=requisitos_json,
            anexos_secao=anexos_secao,
            projeto=parecer.projeto,
            numero_parecer=parecer.numero_parecer,
        )
        logger.info(
            "Resolvendo amarracoes: parecer=%s, %d requisitos, %d anexos (%d chars)",
            parecer.id,
            len(requisitos_base),
            len(anexos),
            sum(len(t) for _, t in anexos),
        )
        resposta = call_llm(
            AMARRACAO_SYSTEM_PROMPT,
            user_content,
            model=settings.GEMINI_EXTRACTION_MODEL,
        )
        resultado = extract_json(resposta)
        merged = _merge_decomposicoes(
            requisitos_base, resultado.get("decomposicoes") or []
        )
        if len(merged) != len(requisitos_base):
            logger.info(
                "Amarracoes resolvidas: %d -> %d requisitos (parecer %s)",
                len(requisitos_base),
                len(merged),
                parecer.id,
            )
        data["requisitos"] = merged
        data["total_itens"] = len(merged)

        refs = [
            str(ref).strip()
            for ref in (resultado.get("referencias_nao_anexadas") or [])
            if str(ref).strip()
        ]
        if refs:
            aviso = (
                f" | Atenção: a MR referencia documento(s) não anexado(s): "
                f"{', '.join(refs)}. Anexe-o(s) como complementar e re-extraia "
                "para decompor os requisitos amarrados."
            )
            data["resumo"] = ((data.get("resumo") or "").strip() + aviso).strip(" |")
    except Exception:
        logger.exception(
            "Passe de amarracoes falhou — mantendo lista base (parecer %s)",
            parecer.id,
        )
    return data


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

    # Passe 2 (ajuste #12): requisitos amarrados a documentos ANEXOS da engenharia
    # ("Sistema CFTV conforme TK-8") sao decompostos no desdobramento real do
    # documento referenciado — nunca ficam como "1 sistema completo".
    anexos, ilegiveis = await _load_anexos_texto(parecer_id, db)
    if anexos and data["requisitos"]:
        relevantes = _anexos_citados(data["requisitos"], anexos)
        total_chars = sum(len(texto) for _, texto in relevantes)
        if relevantes and total_chars <= _ANEXOS_MAX_TOTAL:
            data = await asyncio.to_thread(
                _resolver_amarracoes_sync, data, relevantes, parecer
            )
        elif relevantes:
            logger.warning(
                "Amarracoes puladas: anexos citados somam %d chars (parecer %s)",
                total_chars,
                parecer_id,
            )
            data["resumo"] = (
                (data.get("resumo") or "").strip()
                + " | Atenção: anexos muito extensos — a decomposição automática "
                "de amarrações não foi executada."
            ).strip(" |")
    if ilegiveis:
        data["resumo"] = (
            (data.get("resumo") or "").strip()
            + f" | Atenção: anexo(s) sem texto legível: {', '.join(ilegiveis)}."
        ).strip(" |")

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
