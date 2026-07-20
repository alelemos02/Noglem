"""
Extracao e aprovacao de requisitos de engenharia (blocos 8-10 do fluxo, operacao W1).

A LLM extrai a lista candidata APENAS dos documentos de engenharia. A lista
extraida e persistida imediatamente como RASCUNHO (`aprovado_em IS NULL`) —
visivel e editavel pelo engenheiro (tela ou chat JULIA), sobrevivendo a
recargas. So na aprovacao (W1) os registros ganham `aprovado_em` e viram a
fonte unica de verdade. A analise (R1) le exclusivamente os aprovados.
"""

import json
import logging
import re
import uuid
from datetime import datetime

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.progress import set_progress
from app.models.documento import Documento
from app.models.documento_chunk import DocumentoChunk
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
from app.services.llm_client import call_llm, call_openai, extract_json
from app.services.prompts.extracao import (
    AMARRACAO_SYSTEM_PROMPT,
    AMARRACAO_USER_PROMPT_TEMPLATE,
    EXTRACAO_SYSTEM_PROMPT,
    EXTRACAO_USER_PROMPT_TEMPLATE,
    REVISOR_EXTRACAO_SYSTEM_PROMPT,
    REVISOR_EXTRACAO_USER_PROMPT_TEMPLATE,
)
from app.services.prompts.seguranca import envelopar
from app.services.retriever import retrieve_relevant_chunks_sync

logger = logging.getLogger(__name__)

# Fases em que a lista de requisitos ainda pode ser (re)aprovada — antes de a
# analise inicial rodar, a lista e substituivel; depois, so via revisao de spec (W7).
_FASES_APROVACAO = {"SETUP", "REQUISITOS", "ANALISE"}

# Passe de amarracoes (ajuste #12): requisitos que remetem a documentos ANEXOS
# ("Sistema CFTV conforme TK-8") sao decompostos no desdobramento real do anexo.
# Anexo ate _ANEXO_FULLTEXT_MAX vai INTEIRO no prompt; acima disso os trechos
# relevantes sao recuperados por busca semantica (pgvector) por requisito
# citante — nada de corte cego que perde a tabela-alvo no fim do documento.
_ANEXO_FULLTEXT_MAX = 120_000  # chars: limiar de "anexo pequeno" (vai inteiro)
_ANEXO_MIN_CHARS = 200         # abaixo disso o texto e ilegivel (OCR vazio)
_MAX_SUBS_POR_ITEM = 80        # sanity cap por requisito decomposto
_RAG_TOP_K_POR_REQUISITO = 8   # chunks recuperados por requisito citante
_RAG_MAX_CHUNKS_POR_ANEXO = 40 # bound do prompt por anexo grande
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


def _quer_lista_completa(normalized_profile: str, feedback: str | None) -> bool:
    """O teto de itens do perfil continua valendo MESMO com escopo/feedback. Um
    RECORTE ("so o capitulo 2") deve diminuir a lista, nunca explodi-la — por
    isso o `escopo` NUNCA libera o teto. So o `feedback` (ajuste explicito do
    usuario sobre a lista) ou o perfil `integral` liberam. Antes da separacao
    dos campos, um recorte com a palavra "todos" virava 90+ itens."""
    fb = (feedback or "").strip().lower()
    return normalized_profile == "integral" or any(
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


def _load_eng_text_sync(db: Session, parecer_id) -> str:
    docs = db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    ).scalars().all()
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
    texto_engenharia: str,
    parecer: Parecer,
    perfil_analise: str,
    escopo: str | None,
    feedback: str | None,
) -> dict:
    escopo_section = (
        "\nRECORTE DE ESCOPO PEDIDO PELO USUARIO (aplicar a REGRA FORTE de "
        f"escopo por secao/capitulo/tabela):\n{escopo}\n\n"
        if escopo and escopo.strip()
        else ""
    )
    feedback_section = (
        f"\nFEEDBACK DO USUARIO (incorporar obrigatoriamente):\n{feedback}\n\n"
        if feedback and feedback.strip()
        else ""
    )
    normalized_profile = normalize_analysis_profile(perfil_analise)
    max_itens = get_profile_max_itens(normalized_profile)
    profile_label = get_profile_label(normalized_profile)
    quer_tudo = _quer_lista_completa(normalized_profile, feedback)
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
        escopo_section=escopo_section,
        feedback_section=feedback_section,
        projeto=parecer.projeto,
        numero_parecer=parecer.numero_parecer,
    ) + limit_instruction

    logger.info(
        "Extracao de requisitos via LLM: parecer=%s, modelo=%s, eng_chars=%d, "
        "quer_tudo=%s, escopo=%r, feedback=%r",
        parecer.id,
        settings.GEMINI_EXTRACTION_MODEL,
        len(texto_engenharia),
        quer_tudo,
        (escopo or "")[:140],
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

    resumo = data.get("resumo", "")
    # Trava dura do teto de itens: a RESTRICAO DE VOLUME no prompt e um pedido,
    # nao uma garantia — o modelo pode devolver 12 quando pedimos 10. Cortamos
    # aqui, na lista-base do passe 1 (ja ordenada por relevancia pelo prompt);
    # o passe de amarracoes expande depois livremente (item desdobrado continua
    # sendo UM item detalhado — subs nao contam no teto).
    if not quer_tudo and len(requisitos) > max_itens:
        total_original = len(requisitos)
        logger.warning(
            "Extracao excedeu o teto: %d > %d itens (parecer %s) — cortando",
            total_original,
            max_itens,
            parecer.id,
        )
        requisitos = requisitos[:max_itens]
        for i, item in enumerate(requisitos):
            item["numero"] = i + 1
        resumo = (
            resumo.strip()
            + f" | Modelo retornou {total_original} itens; mantidos os "
            f"{max_itens} mais relevantes (perfil {profile_label})."
        ).strip(" |")

    return {
        "requisitos": requisitos,
        "total_itens": len(requisitos),
        "resumo": resumo,
    }


def _load_anexos_sync(
    db: Session, parecer_id
) -> tuple[list[tuple[str, str]], list[str], dict[str, uuid.UUID]]:
    """Anexos da engenharia legiveis [(nome, texto COMPLETO)], a lista de nomes
    ilegiveis (texto ausente/curto demais — upload sem OCR util) e o mapa
    nome→documento_id (para o retrieval por anexo quando o texto e extenso)."""
    docs = db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    ).scalars().all()
    legiveis: list[tuple[str, str]] = []
    ilegiveis: list[str] = []
    ids_por_nome: dict[str, uuid.UUID] = {}
    for d in anexo_docs_correntes(list(docs)):
        texto = (d.texto_extraido or "").strip()
        if len(texto) < _ANEXO_MIN_CHARS:
            ilegiveis.append(d.nome_arquivo)
        else:
            legiveis.append((d.nome_arquivo, texto))
            ids_por_nome[d.nome_arquivo] = d.id
    return legiveis, ilegiveis, ids_por_nome


_CAMPOS_CITACAO = (
    "descricao_requisito",
    "valor_requerido",
    "referencia_engenharia",
    "norma_referencia",
)


def _stems_do_nome(nome: str) -> set[str]:
    """Stems do nome do arquivo (tokens alfanumericos len>=3 do nome sem
    extensao, incluindo pares adjacentes e o nome colado: "TK-8" vira "tk8")."""
    base = _normalize_text(nome.rsplit(".", 1)[0])
    partes = [p for p in re.split(r"[^a-z0-9]+", base) if p]
    stems = {p for p in partes if len(p) >= 3}
    stems.update(a + b for a, b in zip(partes, partes[1:]) if len(a + b) >= 3)
    return stems


def _texto_de_citacao(requisito: dict) -> str:
    return _normalize_text(
        " ".join(str(requisito.get(campo) or "") for campo in _CAMPOS_CITACAO)
    )


def _anexos_citados(
    requisitos: list[dict], anexos: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Pre-filtro deterministico (zero LLM) do passe de amarracoes.

    Um anexo e candidato quando algum stem do nome do arquivo aparece no texto
    dos requisitos. Sem stem citado mas com palavra-chave generica de
    referencia em algum requisito, todos os anexos entram (o LLM decide). Sem
    nada: passe pulado. Falso positivo aqui e barato — so inclui o anexo na
    chamada batched.
    """
    texto_reqs = _normalize_text(
        " | ".join(
            " ".join(str(r.get(campo) or "") for campo in _CAMPOS_CITACAO)
            for r in requisitos
        )
    )
    texto_reqs_colado = re.sub(r"[^a-z0-9]+", "", texto_reqs)

    citados: list[tuple[str, str]] = []
    for nome, texto in anexos:
        stems = _stems_do_nome(nome)
        if any(s in texto_reqs or s in texto_reqs_colado for s in stems):
            citados.append((nome, texto))

    if not citados and any(k in texto_reqs for k in _REF_KEYWORDS):
        return list(anexos)
    return citados


def _requisitos_citantes(requisitos: list[dict], nome_anexo: str) -> list[dict]:
    """Requisitos que citam o anexo pelo stem do nome (mesma regra do
    pre-filtro _anexos_citados, por requisito). Sem match por stem, caem no
    fallback: requisitos com palavra-chave generica de referencia. Guia as
    queries do retrieval quando o anexo e extenso demais para ir inteiro."""
    stems = _stems_do_nome(nome_anexo)
    citantes = []
    for r in requisitos:
        texto = _texto_de_citacao(r)
        colado = re.sub(r"[^a-z0-9]+", "", texto)
        if any(s in texto or s in colado for s in stems):
            citantes.append(r)
    if not citantes:
        citantes = [
            r for r in requisitos if any(k in _texto_de_citacao(r) for k in _REF_KEYWORDS)
        ]
    return citantes


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


def _requisitos_para_json(requisitos: list[dict]) -> str:
    """Serializacao canonica da lista para prompts (amarracoes e revisor)."""
    return json.dumps(
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
            for r in requisitos
        ],
        ensure_ascii=False,
    )


def _montar_anexos_secao(anexos: list[tuple[str, str]]) -> str:
    """Secao de anexos envelopada (anti-injecao) — compartilhada entre o passe
    de amarracoes e o revisor da extracao (mesmo material para gerador e
    auditor)."""
    return "\n\n".join(
        f"### ANEXO: {nome}\n" + envelopar("DOC_ANEXO_ENGENHARIA", texto)
        for nome, texto in anexos
    )


def _montar_texto_anexo_sync(
    db: Session,
    parecer_id,
    nome: str,
    texto: str,
    doc_id,
    requisitos: list[dict],
) -> tuple[str, str | None]:
    """Texto do anexo que vai ao prompt de amarracoes: inteiro quando pequeno;
    quando extenso, os trechos relevantes recuperados por busca semantica
    (pgvector, filtrada pelo documento) guiada pelos requisitos citantes.

    Devolve (texto_final, aviso|None). Qualquer falha degrada para o corte no
    inicio do texto + aviso — nunca pior do que o comportamento antigo.
    """
    if len(texto) <= _ANEXO_FULLTEXT_MAX:
        return texto, None

    aviso_corte = (
        f"Atenção: anexo {nome} muito extenso — a busca semântica não estava "
        "disponível e apenas o início do texto foi usado na decomposição."
    )
    fallback = texto[:_ANEXO_FULLTEXT_MAX]
    if doc_id is None:
        return fallback, aviso_corte

    try:
        n_chunks = db.execute(
            select(func.count())
            .select_from(DocumentoChunk)
            .where(DocumentoChunk.documento_id == doc_id)
        ).scalar()
        if not n_chunks:
            # Corrida de indexacao: o upload enfileira a indexacao RAG, que pode
            # nao ter terminado. Estamos no worker — indexar inline resolve.
            from app.services.indexer import index_document_sync

            logger.info(
                "Anexo %s sem chunks — indexando inline antes do retrieval", nome
            )
            n_chunks = index_document_sync(str(doc_id))
        if not n_chunks:
            return fallback, aviso_corte

        citantes = _requisitos_citantes(requisitos, nome)
        vistos: set = set()
        selecionados: list[DocumentoChunk] = []
        for r in citantes:
            query = (
                f"{r.get('descricao_requisito') or ''} "
                f"{r.get('valor_requerido') or ''}"
            ).strip()
            if not query:
                continue
            chunks = retrieve_relevant_chunks_sync(
                query,
                parecer_id,
                db,
                documento_ids=[doc_id],
                top_k=_RAG_TOP_K_POR_REQUISITO,
            )
            for c in chunks:
                if c.id in vistos:
                    continue
                vistos.add(c.id)
                selecionados.append(c)
            if len(selecionados) >= _RAG_MAX_CHUNKS_POR_ANEXO:
                break

        if not selecionados:
            return fallback, aviso_corte

        # Apresentacao em ordem de documento (pagina/posicao) — os marcadores de
        # pagina alimentam a regra "pag. N" do prompt de amarracao.
        selecionados = selecionados[:_RAG_MAX_CHUNKS_POR_ANEXO]
        selecionados.sort(key=lambda c: (c.page_number or 0, c.chunk_index))
        blocos = []
        for c in selecionados:
            rotulo = "TABELA" if c.chunk_type == "table" else "TEXTO"
            pagina = f"[Pagina {c.page_number}] " if c.page_number else ""
            blocos.append(f"{pagina}({rotulo})\n{c.conteudo}")
        cabecalho = (
            f"(Anexo extenso — {len(selecionados)} trechos relevantes "
            "recuperados por busca semantica; paginas nos marcadores)"
        )
        logger.info(
            "Anexo %s: %d trechos recuperados por RAG para %d requisitos citantes",
            nome,
            len(selecionados),
            len(citantes),
        )
        return cabecalho + "\n\n" + "\n\n".join(blocos), None
    except Exception:
        logger.exception("Retrieval do anexo %s falhou — usando corte inicial", nome)
        return fallback, aviso_corte


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
        requisitos_json = _requisitos_para_json(requisitos_base)
        anexos_secao = _montar_anexos_secao(anexos)
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


# ─────────────────────────────────────────────────────────────────────────────
# Extracao em background (Celery) — a cadeia de chamadas LLM (extracao +
# amarracoes + revisao) nao pode segurar uma request HTTP. O corpo sync roda no
# worker (app/worker.py, task "extrair_requisitos") e publica progresso em
# Redis na chave `extracao:{parecer_id}` (via set_progress — sem colisao com a
# chave da analise R1, que usa o parecer_id cru).
# ─────────────────────────────────────────────────────────────────────────────

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def progress_key_extracao(parecer_id) -> str:
    """Chave de progresso da extracao — compartilhada entre endpoint e worker."""
    return f"extracao:{parecer_id}"


def _salvar_draft_sync(db: Session, parecer: Parecer, itens: list[dict]) -> int:
    """Espelho sync de salvar_draft para o worker (fase ja validada no corpo)."""
    db.execute(
        delete(Requisito).where(
            Requisito.parecer_id == parecer.id,
            Requisito.aprovado_em.is_(None),
        )
    )
    salvos = 0
    for i, item in enumerate(itens):
        descricao = (item.get("descricao_requisito") or "").strip()
        if not descricao:
            continue
        prioridade = item.get("prioridade")
        db.add(
            Requisito(
                parecer_id=parecer.id,
                numero=i + 1,
                categoria=item.get("categoria"),
                descricao_requisito=descricao,
                referencia_engenharia=item.get("referencia_engenharia"),
                valor_requerido=item.get("valor_requerido"),
                prioridade=prioridade if prioridade in _PRIORIDADES_VALIDAS else "MEDIA",
                norma_referencia=item.get("norma_referencia"),
                aprovado_por=None,
                aprovado_em=None,
            )
        )
        salvos += 1
    return salvos


def _revisar_extracao_sync(
    texto_eng: str,
    data: dict,
    anexos_para_passe: list[tuple[str, str]],
    parecer: Parecer,
    perfil_analise: str,
    escopo: str | None,
    feedback: str | None,
) -> dict | None:
    """Auditoria da lista extraida por um segundo LLM (OpenAI GPT).

    Verifica contagem vs pedido, fidelidade ao documento (dentro do escopo),
    amarracoes vs trechos reais dos anexos e granularidade. Devolve
    {"aprovado": bool, "problemas": [...]} ou None quando desativado/sem chave
    ou em QUALQUER falha — a revisao nunca quebra a extracao (rollback
    operacional: ENABLE_EXTRACTION_REVIEWER=false, sem deploy).
    """
    if not settings.ENABLE_EXTRACTION_REVIEWER or not settings.OPENAI_API_KEY.strip():
        logger.info(
            "Revisor da extracao pulado (flag off ou OPENAI_API_KEY ausente) — "
            "parecer %s",
            parecer.id,
        )
        return None
    try:
        normalized_profile = normalize_analysis_profile(perfil_analise)
        max_itens = get_profile_max_itens(normalized_profile)
        profile_label = get_profile_label(normalized_profile)
        quer_tudo = _quer_lista_completa(normalized_profile, feedback)

        escopo_section = (
            f"- Recorte de escopo pedido pelo usuario: {escopo}\n"
            if escopo and escopo.strip()
            else ""
        )
        feedback_section = (
            f"- Feedback do usuario incorporado: {feedback}\n"
            if feedback and feedback.strip()
            else ""
        )
        user_content = REVISOR_EXTRACAO_USER_PROMPT_TEMPLATE.format(
            texto_engenharia=texto_eng,
            requisitos_json=_requisitos_para_json(data.get("requisitos") or []),
            anexos_secao=(
                _montar_anexos_secao(anexos_para_passe)
                if anexos_para_passe
                else "(nenhum anexo usado no desdobramento)"
            ),
            perfil_label=profile_label,
            max_itens=max_itens,
            sem_teto_flag=(
                " (SEM teto: usuario pediu a lista completa)" if quer_tudo else ""
            ),
            escopo_section=escopo_section,
            feedback_section=feedback_section,
            projeto=parecer.projeto,
            numero_parecer=parecer.numero_parecer,
        )
        logger.info(
            "Revisando extracao: parecer=%s, modelo=%s, %d requisitos, %d anexos",
            parecer.id,
            settings.OPENAI_REVIEWER_MODEL,
            len(data.get("requisitos") or []),
            len(anexos_para_passe),
        )
        resposta = call_openai(REVISOR_EXTRACAO_SYSTEM_PROMPT, user_content)
        veredito = extract_json(resposta)
        problemas = veredito.get("problemas")
        if not isinstance(problemas, list):
            problemas = []
        problemas = [
            p
            for p in problemas
            if isinstance(p, dict) and str(p.get("detalhe") or "").strip()
        ]
        resultado = {"aprovado": bool(veredito.get("aprovado")), "problemas": problemas}
        logger.info(
            "Veredito do revisor (parecer %s): aprovado=%s, %d problema(s)",
            parecer.id,
            resultado["aprovado"],
            len(problemas),
        )
        return resultado
    except Exception:
        logger.exception(
            "Revisor da extracao falhou — draft segue sem revisao (parecer %s)",
            parecer.id,
        )
        return None


def run_extracao_sync(
    parecer_id: str,
    perfil_analise: str,
    escopo: str | None = None,
    feedback: str | None = None,
) -> dict:
    """Extrai a lista candidata de requisitos (blocos 8-9) e persiste como rascunho.

    Corpo da task Celery `extrair_requisitos`. O resumo da extracao viaja na
    mensagem do stage `completed` — e por ele que o frontend o recupera.
    """
    key = progress_key_extracao(parecer_id)
    try:
        with Session(_get_sync_engine()) as db:
            parecer = db.execute(
                select(Parecer).where(Parecer.id == uuid.UUID(parecer_id))
            ).scalar_one_or_none()
            if not parecer:
                raise ValueError("Parecer nao encontrado.")
            if parecer.fase_caso not in _FASES_APROVACAO:
                raise ValueError(
                    f"Extracao de requisitos indisponivel na fase {parecer.fase_caso}. "
                    "Apos a analise, use a revisao de especificacao."
                )

            set_progress(key, 5, "Lendo documentos de engenharia...", "lendo_documento")
            texto_eng = _load_eng_text_sync(db, parecer.id)

            set_progress(key, 20, "Extraindo requisitos do documento...", "extraindo")
            data = _call_extracao_llm(texto_eng, parecer, perfil_analise, escopo, feedback)

            # Passe 2 (ajuste #12): requisitos amarrados a documentos ANEXOS da
            # engenharia ("Sistema CFTV conforme TK-8") sao decompostos no
            # desdobramento real do documento referenciado. Anexo extenso nao
            # pula mais o passe: os trechos relevantes vem por busca semantica.
            anexos, ilegiveis, ids_por_nome = _load_anexos_sync(db, parecer.id)
            anexos_para_passe: list[tuple[str, str]] = []
            avisos_anexos: list[str] = []
            if anexos and data["requisitos"]:
                relevantes = _anexos_citados(data["requisitos"], anexos)
                if relevantes:
                    set_progress(
                        key, 55, "Desdobrando amarrações com os anexos...", "amarracoes"
                    )
                    for nome, texto in relevantes:
                        texto_final, aviso = _montar_texto_anexo_sync(
                            db,
                            parecer.id,
                            nome,
                            texto,
                            ids_por_nome.get(nome),
                            data["requisitos"],
                        )
                        anexos_para_passe.append((nome, texto_final))
                        if aviso:
                            avisos_anexos.append(aviso)
                    data = _resolver_amarracoes_sync(data, anexos_para_passe, parecer)

            # Revisao por um segundo LLM (auditor independente) + UMA rodada de
            # correcao. Falha em qualquer etapa mantem o resultado que ja existia
            # — a contagem final e garantida pelo corte em codigo dentro de
            # _call_extracao_llm, entao nao ha re-revisao.
            set_progress(key, 75, "Revisando a lista com o agente revisor...", "revisando")
            veredito = _revisar_extracao_sync(
                texto_eng, data, anexos_para_passe, parecer,
                perfil_analise, escopo, feedback,
            )
            if veredito and veredito["problemas"]:
                n_problemas = len(veredito["problemas"])
                set_progress(
                    key,
                    85,
                    f"Aplicando correções ({n_problemas} apontamento(s) do revisor)...",
                    "corrigindo",
                )
                try:
                    feedback_correcao = (
                        (feedback or "").strip()
                        + "\n\nREVISAO AUTOMATICA (auditor independente) encontrou "
                        "problemas na lista anterior — corrija EXATAMENTE estes "
                        "pontos, mantendo o restante como esta:\n"
                        + json.dumps(veredito["problemas"], ensure_ascii=False)
                    ).strip()
                    data_corrigida = _call_extracao_llm(
                        texto_eng, parecer, perfil_analise, escopo, feedback_correcao
                    )
                    if anexos_para_passe and data_corrigida["requisitos"]:
                        data_corrigida = _resolver_amarracoes_sync(
                            data_corrigida, anexos_para_passe, parecer
                        )
                    data = data_corrigida
                    data["resumo"] = (
                        (data.get("resumo") or "").strip()
                        + f" | Lista revisada e corrigida automaticamente "
                        f"({n_problemas} apontamento(s) do revisor)."
                    ).strip(" |")
                except Exception:
                    logger.exception(
                        "Rodada de correcao falhou — mantendo lista pre-correcao "
                        "(parecer %s)",
                        parecer_id,
                    )
                    data["resumo"] = (
                        (data.get("resumo") or "").strip()
                        + f" | Atenção: o revisor apontou {n_problemas} problema(s), "
                        "mas a correção automática falhou — confira os itens "
                        "apontados manualmente."
                    ).strip(" |")
            elif veredito and veredito["aprovado"]:
                data["resumo"] = (
                    (data.get("resumo") or "").strip()
                    + " | Lista verificada pelo agente revisor."
                ).strip(" |")

            for aviso in avisos_anexos:
                data["resumo"] = (
                    (data.get("resumo") or "").strip() + f" | {aviso}"
                ).strip(" |")
            if ilegiveis:
                data["resumo"] = (
                    (data.get("resumo") or "").strip()
                    + f" | Atenção: anexo(s) sem texto legível: {', '.join(ilegiveis)}."
                ).strip(" |")

            if parecer.fase_caso == "SETUP":
                parecer.fase_caso = "REQUISITOS"

            # Persiste o rascunho: sobrevive a recargas e fica visivel na tabela
            set_progress(key, 95, "Salvando rascunho de requisitos...", "salvando")
            salvos = _salvar_draft_sync(db, parecer, data["requisitos"])
            db.commit()

            logger.info(
                "Draft de requisitos salvo: %d itens (parecer %s)", salvos, parecer_id
            )
            resumo_final = (data.get("resumo") or "").strip() or "Extração concluída."
            set_progress(key, 100, resumo_final, "completed")
            return {"total_itens": salvos, "resumo": resumo_final}
    except Exception as e:
        logger.exception("Extracao de requisitos falhou (parecer %s)", parecer_id)
        set_progress(key, 100, str(e)[:500] or "Erro na extração.", "error")
        return {"error": str(e)[:500]}


def start_extracao_in_background(
    parecer_id: str,
    perfil_analise: str,
    escopo: str | None = None,
    feedback: str | None = None,
) -> str:
    """Enfileira a extracao no Celery e devolve o task id."""
    from app.worker import extrair_requisitos_task

    task = extrair_requisitos_task.delay(parecer_id, perfil_analise, escopo, feedback)
    return task.id


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
