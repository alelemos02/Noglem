import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.rate_limit import RedisRateLimiter
from app.models.documento import Documento
from app.models.item_parecer import ItemParecer
from app.models.audit_log import AuditLog
from app.models.mensagem_chat import MensagemChat
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.models.revisao import RevisaoParecer
from app.models.usuario import Usuario
from app.schemas.chat import ChatHistoryResponse, ChatMessageResponse, ChatMessageSend
from app.api.v1.endpoints.itens import _recalculate_parecer_summary
from app.services.audit import registrar_auditoria
from app.services import requisitos as requisitos_service
from app.services.state_machine import (
    ANALISE,
    CICLO_FORNECEDOR,
    VERIFICACAO_FINAL,
    todos_aceitos,
)
from app.services.chat import (
    TRANSICOES_POR_STEP,
    build_chat_context,
    call_gemini_json_async,
    call_gemini_stream_async,
    detectar_intencao_extracao,
    detectar_intencao_revisao_spec,
    detectar_intencao_voltar_fase,
    detectar_sem_complementares,
    detectar_transicao_declarada,
    parse_acao_block,
)
from app.services.chat_memory import (
    index_chat_message,
    index_missing_chat_messages,
    retrieve_chat_memory,
    should_retrieve_chat_memory,
)
from app.services.retriever import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pareceres/{parecer_id}/chat", tags=["chat"])

# Rate limiter for chat: 20 messages per 60 seconds per user (compartilhado via Redis)
chat_rate_limiter = RedisRateLimiter(max_requests=20, window_seconds=60, prefix="chat")

# Perfis de extracao validos para a acao extrair_requisitos (espelha o endpoint
# de requisitos). custom_N = N requisitos exatos; integral = a tabela inteira.
_VALID_PROFILE_RE = re.compile(
    r"^(simples|padrao|completa|integral|triagem_tecnica|conformidade_tecnica|"
    r"auditoria_tecnica_completa|custom_\d+)$"
)


async def _check_chat_rate_limit(request: Request, user_id: str):
    key = f"chat:{user_id}"
    allowed, remaining = chat_rate_limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite de mensagens excedido. "
                f"Maximo de {chat_rate_limiter.max_requests} mensagens "
                f"por {chat_rate_limiter.window_seconds} segundos."
            ),
            headers={"Retry-After": str(chat_rate_limiter.window_seconds)},
        )


def _acao_valida(payload) -> bool:
    """Valida o shape das ações que a JULIA pode emitir via chat."""
    if not isinstance(payload, dict):
        return False
    tipo = payload.get("tipo")
    if tipo == "atualizar_requisitos":
        return isinstance(payload.get("requisitos"), list)
    if tipo == "atualizar_itens":
        return isinstance(payload.get("itens"), list)
    return tipo in {
        "aprovar_requisitos",
        "iniciar_ciclo",
        "revisar_especificacao",
        "reanalisar",
        "reabrir_requisitos",
        "extrair_requisitos",
        "confirmar_complementares",
    }


# Campos de ItemParecer que a JULIA pode corrigir via patch
_CAMPOS_ITEM_PATCH = {
    "status",
    "justificativa_tecnica",
    "acao_requerida",
    "prioridade",
    "valor_requerido",
    "valor_fornecedor",
    "norma_referencia",
    "descricao_requisito",
}
_STATUS_VALIDOS = {"A", "B", "C", "D", "E"}
_PRIORIDADES_VALIDAS = {"ALTA", "MEDIA", "BAIXA"}


async def _executar_acao(
    db: AsyncSession,
    parecer_id: uuid.UUID,
    acao: dict,
    current_user: Usuario,
) -> dict:
    """Executa uma ação da JULIA direto no banco e retorna o evento SSE.

    - atualizar_requisitos: substitui o rascunho (W1 pendente)
    - aprovar_requisitos: aprova o rascunho (W1) — fase vai para ANALISE;
      o frontend dispara a análise R1 ao receber o evento
    - iniciar_ciclo: W2 — ANALISE → CICLO_FORNECEDOR (ou VERIFICACAO_FINAL
      se 100% dos itens já estão aceitos)
    """
    tipo = acao.get("tipo")

    if tipo == "atualizar_requisitos":
        salvos = await requisitos_service.salvar_draft(
            parecer_id, db, acao.get("requisitos") or []
        )
        return {"tipo": tipo, "total": len(salvos)}

    if tipo == "aprovar_requisitos":
        draft = await requisitos_service.listar_draft(parecer_id, db)
        if not draft:
            raise ValueError("Nao ha rascunho de requisitos para aprovar.")
        itens = [
            {
                "categoria": r.categoria,
                "descricao_requisito": r.descricao_requisito,
                "referencia_engenharia": r.referencia_engenharia,
                "valor_requerido": r.valor_requerido,
                "prioridade": r.prioridade,
                "norma_referencia": r.norma_referencia,
            }
            for r in draft
        ]
        parecer, aprovados = await requisitos_service.aprovar_requisitos(
            parecer_id, db, itens, current_user
        )
        logger.info(
            "W1 via chat: %d requisitos aprovados (parecer %s)",
            len(aprovados),
            parecer_id,
        )
        return {
            "tipo": tipo,
            "total": len(aprovados),
            "fase_caso": parecer.fase_caso,
        }

    if tipo == "atualizar_itens":
        patches = acao.get("itens") or []
        atualizados = 0
        for patch in patches:
            if not isinstance(patch, dict) or "numero" not in patch:
                continue
            result = await db.execute(
                select(ItemParecer).where(
                    ItemParecer.parecer_id == parecer_id,
                    ItemParecer.numero == patch["numero"],
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                continue
            campos = {
                k: v for k, v in patch.items() if k in _CAMPOS_ITEM_PATCH
            }
            if "status" in campos and campos["status"] not in _STATUS_VALIDOS:
                campos.pop("status")
            if (
                "prioridade" in campos
                and campos["prioridade"] not in _PRIORIDADES_VALIDAS
            ):
                campos.pop("prioridade")
            if not campos:
                continue
            status_anterior = item.status
            estado_anterior = item.estado
            prioridade_anterior = item.prioridade
            for campo, valor in campos.items():
                setattr(item, campo, valor)
            item.editado_manualmente = True
            if {"status", "prioridade"} & set(campos):
                await registrar_auditoria(
                    db,
                    current_user,
                    "item_atualizacao_via_julia",
                    "item",
                    recurso_id=str(item.id),
                    detalhes=(
                        f"item_numero={item.numero}; origem=chat_julia; "
                        f"status_anterior={status_anterior}; status_novo={item.status}; "
                        f"estado_anterior={estado_anterior}; estado_novo={item.estado}; "
                        f"prioridade_anterior={prioridade_anterior}; prioridade_nova={item.prioridade}"
                    ),
                )
            atualizados += 1
        if atualizados == 0:
            raise ValueError("Nenhum item correspondente para atualizar.")
        await db.commit()
        await _recalculate_parecer_summary(parecer_id, db)
        logger.info(
            "%d itens corrigidos via chat (parecer %s)", atualizados, parecer_id
        )
        return {"tipo": tipo, "total": atualizados}

    if tipo == "revisar_especificacao":
        # Acao de UI: nao muta o banco. O frontend abre o envio da nova revisao
        # (o engenheiro anexa o arquivo; a comparacao R4 roda em seguida).
        return {"tipo": tipo}

    if tipo == "reanalisar":
        # Acao de UI: o frontend redispara a analise R1 (mesmo caminho do
        # comando "reanalisar"), com validacao de fase e barra de progresso.
        # Nao muta o banco aqui — evita despejo de JSON no chat.
        return {"tipo": tipo}

    if tipo == "extrair_requisitos":
        # Acao de UI (passo setup.extrair): o frontend dispara a extracao com o
        # perfil escolhido na conversa e mostra o progresso. Nao muta o banco aqui.
        # `escopo` carrega o recorte que o usuario pediu (capitulo/tabela/faixa) e
        # vira o feedback da extracao — e o que ativa a "REGRA FORTE" de recorte
        # por secao e a enumeracao linha-a-linha. Sem ele a extracao pega o doc todo.
        perfil = str(acao.get("perfil") or "padrao").strip()
        if not _VALID_PROFILE_RE.match(perfil):
            perfil = "padrao"
        escopo = str(acao.get("escopo") or "").strip()
        if escopo.lower() in ("", "documento inteiro", "documento todo", "nenhum", "sem recorte"):
            escopo = None
        return {"tipo": tipo, "perfil": perfil, "escopo": escopo}

    if tipo == "confirmar_complementares":
        # Gate de setup: marca que os documentos complementares foram resolvidos
        # (anexados ou declarados inexistentes) — libera a etapa do fornecedor.
        result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
        parecer_obj = result.scalar_one_or_none()
        if parecer_obj:
            parecer_obj.complementares_resolvidos = True
            await db.commit()
        return {"tipo": tipo}

    if tipo == "reabrir_requisitos":
        # Reabre a lista de requisitos aprovados como rascunho editavel (fase
        # ANALISE): o RequisitosWidget reaparece para o engenheiro editar a lista
        # (sem comparacao) e, ao aprovar, a analise e refeita. Bloqueado no ciclo.
        draft = await requisitos_service.reabrir_requisitos(parecer_id, db)
        return {"tipo": tipo, "total": len(draft)}

    if tipo == "iniciar_ciclo":
        result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
        parecer = result.scalar_one_or_none()
        if not parecer:
            raise ValueError("Parecer nao encontrado.")
        if parecer.fase_caso != ANALISE:
            raise ValueError(
                f"Ciclo so pode ser iniciado na fase ANALISE (atual: {parecer.fase_caso})."
            )
        if parecer.status_processamento != "concluido" or (parecer.total_itens or 0) == 0:
            raise ValueError("Execute a analise antes de iniciar o ciclo.")

        estados_result = await db.execute(
            select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
        )
        estados = [row[0] for row in estados_result.all()]
        parecer.fase_caso = (
            VERIFICACAO_FINAL if todos_aceitos(estados) else CICLO_FORNECEDOR
        )
        await db.commit()
        logger.info(
            "W2 via chat: parecer %s -> %s", parecer_id, parecer.fase_caso
        )
        return {"tipo": tipo, "fase_caso": parecer.fase_caso}

    raise ValueError(f"Acao desconhecida: {tipo}")


async def _get_parecer(
    parecer_id: uuid.UUID, db: AsyncSession, exigir_concluido: bool = False
) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    if exigir_concluido and parecer.status_processamento != "concluido":
        raise HTTPException(
            status_code=400,
            detail="Operacao disponivel apenas para pareceres com analise concluida",
        )
    return parecer


@router.get("/historico", response_model=ChatHistoryResponse)
async def listar_historico(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_user),
):
    """Retorna o historico de mensagens do chat para um parecer."""
    result = await db.execute(
        select(MensagemChat)
        .where(MensagemChat.parecer_id == parecer_id)
        .order_by(MensagemChat.ordem)
    )
    mensagens = result.scalars().all()

    return ChatHistoryResponse(
        messages=[
            ChatMessageResponse(
                id=str(m.id),
                papel=m.papel,
                conteudo=m.conteudo,
                ordem=m.ordem,
                gerou_nova_tabela=m.gerou_nova_tabela,
                criado_em=m.criado_em,
            )
            for m in mensagens
        ],
        total=len(mensagens),
    )


@router.post("/mensagem")
async def enviar_mensagem(
    parecer_id: uuid.UUID,
    payload: ChatMessageSend,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Envia uma mensagem e retorna a resposta da IA via SSE streaming.

    Com `contexto` (modo JULIA), o chat funciona em qualquer fase do caso e
    pode emitir acoes estruturadas (ex: atualizar o draft de requisitos W1).
    """
    await _check_chat_rate_limit(request, str(current_user.id))

    parecer = await _get_parecer(parecer_id, db)

    # Load current items, recommendations, documents
    itens_result = await db.execute(
        select(ItemParecer)
        .where(ItemParecer.parecer_id == parecer_id)
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()
    item_ids = [str(item.id) for item in itens]

    audit_logs = []
    if item_ids:
        audit_result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.recurso == "item",
                AuditLog.recurso_id.in_(item_ids),
                AuditLog.acao.in_(
                    [
                        "w4_decidir_item",
                        "item_atualizacao_manual",
                        "item_atualizacao_via_julia",
                    ]
                ),
            )
            .order_by(AuditLog.criado_em.desc())
            .limit(100)
        )
        audit_logs = list(reversed(audit_result.scalars().all()))

    recs_result = await db.execute(
        select(Recomendacao)
        .where(Recomendacao.parecer_id == parecer_id)
        .order_by(Recomendacao.ordem)
    )
    recomendacoes = recs_result.scalars().all()

    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    documentos = docs_result.scalars().all()

    # Load existing chat messages
    msgs_result = await db.execute(
        select(MensagemChat)
        .where(MensagemChat.parecer_id == parecer_id)
        .order_by(MensagemChat.ordem)
    )
    mensagens = msgs_result.scalars().all()

    # Determine next order number
    max_ordem_result = await db.execute(
        select(func.coalesce(func.max(MensagemChat.ordem), 0))
        .where(MensagemChat.parecer_id == parecer_id)
    )
    next_ordem = max_ordem_result.scalar() + 1

    # Save user message
    user_msg = MensagemChat(
        parecer_id=parecer_id,
        usuario_id=current_user.id,
        papel="user",
        conteudo=payload.mensagem,
        ordem=next_ordem,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Trava deterministica: o fluxo so anda PARA FRENTE. Se o usuario pedir para
    # voltar de fase / cancelar o ciclo (transicao inexistente), a JULIA declina com
    # honestidade ANTES de chamar o LLM — senao o modelo promete revertar e falha,
    # disparando o aviso amarelo. So vale nas fases de onde nao ha caminho de volta.
    if parecer.fase_caso in (
        CICLO_FORNECEDOR,
        VERIFICACAO_FINAL,
    ) and detectar_intencao_voltar_fase(payload.mensagem):
        logger.info(
            "Pedido de voltar/cancelar fase detectado em %s — declinando (parecer %s)",
            parecer.fase_caso,
            parecer_id,
        )
        return StreamingResponse(
            _stream_voltar_fase_indisponivel(parecer_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    retrieved_chat_memories = []
    if should_retrieve_chat_memory(payload.mensagem):
        try:
            indexed = await index_missing_chat_messages(parecer_id, db)
            if indexed:
                await db.commit()
            recent = mensagens[-20:] if len(mensagens) > 20 else mensagens
            exclude_ids = {m.id for m in recent}
            exclude_ids.add(user_msg.id)
            retrieved_chat_memories = await retrieve_chat_memory(
                query=payload.mensagem,
                parecer_id=parecer_id,
                db=db,
                exclude_message_ids=exclude_ids,
            )
        except Exception:
            logger.exception(
                "Falha ao recuperar memoria semantica do chat (parecer %s)",
                parecer_id,
            )
            await db.rollback()

    # Retrieve relevant chunks via RAG (pre-analise o indice pgvector ainda nao
    # existe -> fallback para texto completo em build_chat_context)
    chunks = None
    if parecer.status_processamento == "concluido":
        try:
            chunks = await retrieve_relevant_chunks(
                query=payload.mensagem,
                parecer_id=parecer_id,
                db=db,
            )
        except Exception:
            logger.exception("RAG retrieval failed for parecer %s, falling back to full text", parecer_id)
            chunks = None

    # Build context with RAG chunks or full text fallback
    system_prompt, contents = build_chat_context(
        parecer=parecer,
        itens=list(itens),
        recomendacoes=list(recomendacoes),
        documentos=list(documentos),
        mensagens=list(mensagens),
        nova_mensagem=payload.mensagem,
        retrieved_chunks=chunks if chunks else None,
        retrieved_chat_memories=retrieved_chat_memories,
        audit_logs=audit_logs,
        contexto_fluxo=payload.contexto.model_dump() if payload.contexto else None,
    )

    # Com draft de requisitos em revisao, a acao reemite a lista COMPLETA —
    # precisa de espaco de saida (8192 truncava o JSON em listas grandes)
    tem_draft = bool(payload.contexto and payload.contexto.requisitos_draft)
    max_tokens = 65536 if tem_draft else 8192

    ACAO_OPEN = "<acao>"
    ACAO_CLOSE = "</acao>"

    async def generate_sse():
        # Streaming com filtro do bloco <acao>: o texto visivel e emitido como
        # chunks; o bloco de acao e retido e emitido como evento estruturado.
        visible_parts: list[str] = []
        pending = ""
        in_action = False
        try:
            async for chunk in call_gemini_stream_async(
                system_prompt, contents, max_tokens=max_tokens
            ):
                pending += chunk
                if in_action:
                    continue  # acumula o bloco de acao ate o fim do stream
                idx = pending.find(ACAO_OPEN)
                if idx != -1:
                    visible = pending[:idx]
                    pending = pending[idx:]
                    in_action = True
                else:
                    # retem um sufixo que pode ser inicio de "<acao>" cortado
                    keep = 0
                    for k in range(min(len(ACAO_OPEN) - 1, len(pending)), 0, -1):
                        if pending.endswith(ACAO_OPEN[:k]):
                            keep = k
                            break
                    visible = pending[: len(pending) - keep]
                    pending = pending[len(pending) - keep:] if keep else ""
                if visible:
                    visible_parts.append(visible)
                    yield f"event: chunk\ndata: {json.dumps({'text': visible}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Chat streaming error for parecer %s", parecer_id)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)[:500]}, ensure_ascii=False)}\n\n"
            return

        # Fim do stream: resolve o restante (texto ou bloco de acao)
        acao_payload = None
        acao_falhou = False
        if in_action:
            raw = pending[len(ACAO_OPEN):]
            end = raw.find(ACAO_CLOSE)
            if end != -1:
                raw = raw[:end]
            acao_payload = parse_acao_block(raw)
            if acao_payload is None:
                # Bloco truncado/invalido: repara com chamada JSON dedicada
                logger.warning(
                    "Bloco <acao> invalido no chat do parecer %s — reparando",
                    parecer_id,
                )
                try:
                    repair_contents = contents + [
                        {"role": "model", "parts": [{"text": "".join(visible_parts) + ACAO_OPEN + raw[:2000]}]},
                        {"role": "user", "parts": [{"text": (
                            "Sua acao foi cortada ou veio invalida. Emita SOMENTE o "
                            "objeto JSON completo e valido da acao, no formato "
                            '{"tipo": "atualizar_requisitos", "requisitos": [...]} '
                            "com a lista COMPLETA de requisitos ja atualizada "
                            "conforme o que voce descreveu na resposta."
                        )}]},
                    ]
                    acao_payload = await call_gemini_json_async(
                        system_prompt, repair_contents
                    )
                except Exception:
                    logger.exception(
                        "Repair da acao falhou no parecer %s", parecer_id
                    )
                if not _acao_valida(acao_payload):
                    acao_payload = None
                    acao_falhou = True
        elif pending:
            visible_parts.append(pending)
            yield f"event: chunk\ndata: {json.dumps({'text': pending}, ensure_ascii=False)}\n\n"

        response_text = "".join(visible_parts).strip()
        if not response_text and acao_payload:
            response_text = "(JULIA atualizou a lista de requisitos em revisao.)"

        # Rede de segurança: a LLM declarou uma transição ("Aprovado! Já estou
        # iniciando...") mas esqueceu o bloco <acao> — detecta e executa mesmo
        # assim, para a promessa nunca ficar sem efeito
        if (
            acao_payload is None
            and not acao_falhou
            and response_text
            and payload.contexto
            and payload.contexto.step_id
        ):
            transicoes = TRANSICOES_POR_STEP.get(payload.contexto.step_id, [])
            if transicoes:
                try:
                    tipo_detectado = await detectar_transicao_declarada(
                        payload.mensagem, response_text, transicoes
                    )
                    if tipo_detectado:
                        logger.info(
                            "Transicao '%s' detectada via classificador (parecer %s)",
                            tipo_detectado,
                            parecer_id,
                        )
                        acao_payload = {"tipo": tipo_detectado}
                except Exception:
                    logger.exception(
                        "Classificador de transicao falhou (parecer %s)", parecer_id
                    )

        # Rede de seguranca: o usuario quer subir/revisar o documento da
        # engenharia, mas a LLM nao abriu o upload (respondeu "cole o texto" em
        # vez de emitir a acao). Detecta a intencao por palavras-chave e abre o
        # envio da nova revisao — so vale pos-analise, com o caso aberto e sem
        # outra revisao ja em andamento.
        if (
            acao_payload is None
            and not acao_falhou
            and payload.contexto
            and parecer.total_itens > 0
            and parecer.fase_caso in (ANALISE, CICLO_FORNECEDOR, VERIFICACAO_FINAL)
            and not getattr(parecer, "revisao_spec_em_andamento", False)
            and detectar_intencao_revisao_spec(payload.mensagem)
        ):
            logger.info(
                "Intencao de revisao de spec detectada — abrindo upload (parecer %s)",
                parecer_id,
            )
            acao_payload = {"tipo": "revisar_especificacao"}
            extra = (
                "\n\nAbri o envio da nova revisão aqui embaixo — é só anexar o "
                "arquivo (PDF, DOCX ou XLSX) que eu comparo com os requisitos "
                "aprovados e te mostro o que mudou antes de aplicar."
            )
            response_text = (response_text + extra).strip()
            yield f"event: chunk\ndata: {json.dumps({'text': extra}, ensure_ascii=False)}\n\n"

        # Rede de seguranca: no passo setup.docs_complementares, o usuario disse que
        # nao tem complementares / pode seguir, mas a LLM nao emitiu o bloco <acao>.
        # Confirma deterministicamente para liberar a etapa do fornecedor.
        if (
            acao_payload is None
            and not acao_falhou
            and payload.contexto
            and payload.contexto.step_id == "setup.docs_complementares"
            and detectar_sem_complementares(payload.mensagem)
        ):
            logger.info(
                "Sem complementares detectado deterministicamente (parecer %s)",
                parecer_id,
            )
            acao_payload = {"tipo": "confirmar_complementares"}

        # Rede de seguranca: no passo setup.extrair o usuario respondeu quantos
        # requisitos quer (um numero, "todos" ou "escolhe voce"), mas a LLM nao
        # emitiu o bloco <acao>. Dispara a extracao deterministicamente para o
        # pedido nunca ficar sem efeito (ver _JULIA_ACAO_EXTRAIR).
        if (
            acao_payload is None
            and not acao_falhou
            and payload.contexto
            and payload.contexto.step_id == "setup.extrair"
        ):
            perfil_det = detectar_intencao_extracao(payload.mensagem)
            if perfil_det:
                logger.info(
                    "Extracao detectada deterministicamente (perfil=%s, parecer %s)",
                    perfil_det,
                    parecer_id,
                )
                # Rede de seguranca para o escopo: se a LLM nao emitiu o bloco, a
                # propria mensagem do usuario ("todos os itens da tabela do cap 2")
                # vira o feedback da extracao — assim o recorte nunca se perde.
                acao_payload = {
                    "tipo": "extrair_requisitos",
                    "perfil": perfil_det,
                    "escopo": payload.mensagem.strip() or None,
                }

        # Save assistant message (use a new session to avoid stale state)
        from app.core.database import async_session
        async with async_session() as save_db:
            # Get next ordem again (in case of concurrent messages)
            max_result = await save_db.execute(
                select(func.coalesce(func.max(MensagemChat.ordem), 0))
                .where(MensagemChat.parecer_id == parecer_id)
            )
            assistant_ordem = max_result.scalar() + 1

            assistant_msg = MensagemChat(
                parecer_id=parecer_id,
                usuario_id=None,
                papel="assistant",
                conteudo=response_text,
                ordem=assistant_ordem,
                gerou_nova_tabela=False,
            )
            save_db.add(assistant_msg)
            await save_db.commit()
            await save_db.refresh(assistant_msg)
            indexed_user = False
            saved_user_msg = await save_db.get(MensagemChat, user_msg.id)
            if saved_user_msg:
                indexed_user = await index_chat_message(saved_user_msg, save_db)
            indexed_assistant = await index_chat_message(assistant_msg, save_db)
            if indexed_user or indexed_assistant:
                await save_db.commit()

            # A conversa muta o estado EXCLUSIVAMENTE por acoes <acao> + widgets
            # (nunca por JSON de tabela no chat — o caminho legado destruia a
            # maquina de estados e o historico do item; ver B4).
            if acao_payload:
                try:
                    evento = await _executar_acao(
                        save_db, parecer_id, acao_payload, current_user
                    )
                    yield f"event: action\ndata: {json.dumps(evento, ensure_ascii=False)}\n\n"
                except Exception:
                    logger.exception(
                        "Falha ao executar acao '%s' via chat (parecer %s)",
                        acao_payload.get("tipo"),
                        parecer_id,
                    )
                    yield f"event: action_error\ndata: {json.dumps({'detail': 'A acao nao pode ser aplicada'}, ensure_ascii=False)}\n\n"
            elif acao_falhou:
                yield f"event: action_error\ndata: {json.dumps({'detail': 'A acao nao pode ser aplicada'}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'message_id': str(assistant_msg.id), 'table_updated': False}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


_MSG_VOLTAR_FASE_INDISPONIVEL = (
    "Não consigo voltar o caso para a fase de Análise por aqui — o fluxo do parecer "
    "só avança, e cancelar o ciclo apagaria o histórico de rodadas e avaliações já "
    "feitas com o fornecedor.\n\n"
    "Mas dá para corrigir o que está errado **sem sair do ciclo**:\n\n"
    "• **Item mal classificado?** Me diga qual item e o que está errado (ex.: \"o item 4 "
    "deveria ser status C\") que eu corrijo o status e a justificativa na hora.\n"
    "• **O documento da engenharia mudou?** Peça para *revisar a especificação* — eu "
    "comparo a nova revisão com os requisitos aprovados e reabro só os itens afetados, "
    "preservando o histórico.\n\n"
    "Qual desses é o seu caso?"
)


async def _stream_voltar_fase_indisponivel(parecer_id: uuid.UUID):
    """SSE canned (sem LLM, sem ação): o fluxo não tem volta de fase. Persiste a
    resposta e fecha com `done` — sem `action_error`, então não dispara o aviso
    amarelo de 'não consegui aplicar a mudança'."""
    msg = _MSG_VOLTAR_FASE_INDISPONIVEL
    yield f"event: chunk\ndata: {json.dumps({'text': msg}, ensure_ascii=False)}\n\n"

    from app.core.database import async_session
    async with async_session() as save_db:
        max_result = await save_db.execute(
            select(func.coalesce(func.max(MensagemChat.ordem), 0))
            .where(MensagemChat.parecer_id == parecer_id)
        )
        ordem = max_result.scalar() + 1
        assistant_msg = MensagemChat(
            parecer_id=parecer_id,
            usuario_id=None,
            papel="assistant",
            conteudo=msg,
            ordem=ordem,
        )
        save_db.add(assistant_msg)
        await save_db.commit()
        await save_db.refresh(assistant_msg)
        yield (
            "event: done\n"
            f"data: {json.dumps({'message_id': str(assistant_msg.id), 'table_updated': False}, ensure_ascii=False)}\n\n"
        )


@router.delete("/historico", status_code=status.HTTP_204_NO_CONTENT)
async def limpar_historico(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(require_role("admin", "analista")),
):
    """Limpa o historico de chat de um parecer."""
    await db.execute(
        delete(MensagemChat).where(MensagemChat.parecer_id == parecer_id)
    )
    await db.commit()


async def _create_auto_revision(
    db: AsyncSession,
    parecer_id: uuid.UUID,
    user_id: uuid.UUID,
):
    """Create an automatic revision snapshot before chat-triggered table update."""
    parecer = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer.scalar_one()

    max_rev_result = await db.execute(
        select(func.coalesce(func.max(RevisaoParecer.numero_revisao), 0))
        .where(RevisaoParecer.parecer_id == parecer_id)
    )
    next_rev = max_rev_result.scalar() + 1

    itens_result = await db.execute(
        select(ItemParecer)
        .where(ItemParecer.parecer_id == parecer_id)
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()
    itens_snapshot = [
        {
            "numero": item.numero,
            "categoria": item.categoria,
            "descricao_requisito": item.descricao_requisito,
            "referencia_engenharia": item.referencia_engenharia,
            "referencia_fornecedor": item.referencia_fornecedor,
            "valor_requerido": item.valor_requerido,
            "valor_fornecedor": item.valor_fornecedor,
            "status": item.status,
            "justificativa_tecnica": item.justificativa_tecnica,
            "acao_requerida": item.acao_requerida,
            "prioridade": item.prioridade,
            "norma_referencia": item.norma_referencia,
            "editado_manualmente": item.editado_manualmente,
        }
        for item in itens
    ]

    recs_result = await db.execute(
        select(Recomendacao)
        .where(Recomendacao.parecer_id == parecer_id)
        .order_by(Recomendacao.ordem)
    )
    recs = recs_result.scalars().all()
    recs_snapshot = [{"ordem": r.ordem, "texto": r.texto} for r in recs]

    revisao = RevisaoParecer(
        parecer_id=parecer_id,
        numero_revisao=next_rev,
        motivo="Revisao automatica antes de atualizacao via chat",
        criado_por=user_id,
        parecer_geral=parecer.parecer_geral,
        comentario_geral=parecer.comentario_geral,
        conclusao=parecer.conclusao,
        total_itens=parecer.total_itens,
        total_aprovados=parecer.total_aprovados,
        total_aprovados_comentarios=parecer.total_aprovados_comentarios,
        total_rejeitados=parecer.total_rejeitados,
        total_info_ausente=parecer.total_info_ausente,
        total_itens_adicionais=parecer.total_itens_adicionais,
        itens_snapshot=itens_snapshot,
        recomendacoes_snapshot=recs_snapshot,
    )
    db.add(revisao)
    await db.commit()
