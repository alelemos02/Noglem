import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.rate_limit import InMemoryRateLimiter
from app.models.documento import Documento
from app.models.item_parecer import ItemParecer
from app.models.mensagem_chat import MensagemChat
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.models.revisao import RevisaoParecer
from app.models.usuario import Usuario
from app.schemas.chat import ChatHistoryResponse, ChatMessageResponse, ChatMessageSend
from app.services.chat import (
    apply_table_update,
    build_chat_context,
    call_gemini_stream_async,
    detect_table_regeneration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pareceres/{parecer_id}/chat", tags=["chat"])

# Rate limiter for chat: 20 messages per 60 seconds per user
chat_rate_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)


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


async def _get_parecer_concluido(parecer_id: uuid.UUID, db: AsyncSession) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    if parecer.status_processamento != "concluido":
        raise HTTPException(
            status_code=400,
            detail="Chat disponivel apenas para pareceres com analise concluida",
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
    """Envia uma mensagem e retorna a resposta da IA via SSE streaming."""
    await _check_chat_rate_limit(request, str(current_user.id))

    parecer = await _get_parecer_concluido(parecer_id, db)

    # Load current items, recommendations, documents
    itens_result = await db.execute(
        select(ItemParecer)
        .where(ItemParecer.parecer_id == parecer_id)
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()

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

    # Build context
    system_prompt, contents = build_chat_context(
        parecer=parecer,
        itens=list(itens),
        recomendacoes=list(recomendacoes),
        documentos=list(documentos),
        mensagens=list(mensagens),
        nova_mensagem=payload.mensagem,
        incluir_documentos=payload.regenerar,
    )

    max_tokens = 65536 if payload.regenerar else 8192

    async def generate_sse():
        full_response = []
        try:
            async for chunk in call_gemini_stream_async(
                system_prompt, contents, max_tokens=max_tokens
            ):
                full_response.append(chunk)
                yield f"event: chunk\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Chat streaming error for parecer %s", parecer_id)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)[:500]}, ensure_ascii=False)}\n\n"
            return

        response_text = "".join(full_response)

        # Save assistant message (use a new session to avoid stale state)
        from app.core.database import async_session
        async with async_session() as save_db:
            # Get next ordem again (in case of concurrent messages)
            max_result = await save_db.execute(
                select(func.coalesce(func.max(MensagemChat.ordem), 0))
                .where(MensagemChat.parecer_id == parecer_id)
            )
            assistant_ordem = max_result.scalar() + 1

            table_updated = False
            new_table = None

            if payload.regenerar:
                new_table = detect_table_regeneration(response_text)

            if new_table:
                table_updated = True

            assistant_msg = MensagemChat(
                parecer_id=parecer_id,
                usuario_id=None,
                papel="assistant",
                conteudo=response_text,
                ordem=assistant_ordem,
                gerou_nova_tabela=table_updated,
            )
            save_db.add(assistant_msg)
            await save_db.commit()
            await save_db.refresh(assistant_msg)

            if table_updated and new_table:
                # Create revision snapshot before applying changes
                await _create_auto_revision(save_db, parecer_id, current_user.id)
                # Apply table update using sync session (apply_table_update uses sync ORM)
                from sqlalchemy import create_engine
                from sqlalchemy.orm import Session as SyncSession
                sync_engine = create_engine(
                    str(settings.DATABASE_URL_SYNC)
                )
                with SyncSession(sync_engine) as sync_db:
                    sync_parecer = sync_db.execute(
                        select(Parecer).where(Parecer.id == parecer_id)
                    ).scalar_one()
                    apply_table_update(sync_db, sync_parecer, new_table)
                sync_engine.dispose()

                yield f"event: table_updated\ndata: {json.dumps({'message_id': str(assistant_msg.id)}, ensure_ascii=False)}\n\n"
            else:
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
