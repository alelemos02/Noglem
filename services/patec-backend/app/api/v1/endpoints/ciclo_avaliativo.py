"""
Endpoints do ciclo iterativo de avaliação de pareceres técnicos.

GET  /{parecer_id}/exportar/carta-pendencias
    Exporta planilha xlsx com itens PENDENTE_FORNECEDOR para envio ao fornecedor.
    Coluna F editável; coluna G (ITEM_ID) oculta para reimport determinístico.

POST /{parecer_id}/reimportar-respostas
    Recebe o xlsx preenchido pelo fornecedor, cria uma RodadaAvaliacao por item
    respondido, chama o Agente Avaliador e atualiza o estado do item para
    EM_REAVALIACAO. Itens sem ITEM_ID válido são sinalizados para resolução manual.
"""
import asyncio
import io
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.rodada_avaliacao import RodadaAvaliacao
from app.services.evaluator import avaliar_resposta
from app.services.exporter import export_carta_pendencias
from app.services.state_machine import (
    PENDENTE_FORNECEDOR,
    EM_REAVALIACAO,
    compute_status_global,
    transicionar,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pareceres", tags=["ciclo-avaliativo"])

# Posições das colunas na carta de pendências (1-based)
_COL_RESPOSTA = 6
_COL_ITEM_ID = 7
# Linha onde começam os dados (1=instrução, 2=cabeçalho, 3+=dados)
_DATA_START_ROW = 3


# ──────────────────────────────────────────────────────────────────────────────
# 2B — Export carta de pendências
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{parecer_id}/exportar/carta-pendencias")
async def exportar_carta_pendencias(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    itens_result = await db.execute(
        select(ItemParecer)
        .where(
            ItemParecer.parecer_id == parecer_id,
            ItemParecer.estado == PENDENTE_FORNECEDOR,
        )
        .order_by(ItemParecer.numero)
    )
    itens_pendentes = itens_result.scalars().all()

    if not itens_pendentes:
        raise HTTPException(
            status_code=400,
            detail="Nenhum item com estado PENDENTE_FORNECEDOR. Nada a exportar.",
        )

    try:
        content = export_carta_pendencias(parecer, itens_pendentes)
    except Exception:
        logger.exception("Falha ao exportar carta de pendencias para parecer %s", parecer_id)
        raise HTTPException(status_code=500, detail="Erro ao gerar carta de pendencias")

    rodada = getattr(parecer, "rodada_atual", 1)
    filename = f"carta_pendencias_{parecer.numero_parecer}_R{rodada}.xlsx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ──────────────────────────────────────────────────────────────────────────────
# 2C — Reimport respostas do fornecedor
# ──────────────────────────────────────────────────────────────────────────────

class ItemProcessado(BaseModel):
    item_id: str
    numero: int
    veredito_ia: str
    justificativa_ia: str
    acao_requerida: str | None


class ItemIgnorado(BaseModel):
    linha: int
    motivo: str
    item_id_raw: str | None = None


class ReimportResult(BaseModel):
    processados: list[ItemProcessado]
    ignorados: list[ItemIgnorado]
    total_processados: int
    total_ignorados: int
    mensagem: str


@router.post("/{parecer_id}/reimportar-respostas", response_model=ReimportResult)
async def reimportar_respostas(
    parecer_id: uuid.UUID,
    arquivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_role("admin", "analista")),
):
    if not (arquivo.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .xlsx sao aceitos.")

    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    if parecer.status_processamento == "processando":
        raise HTTPException(status_code=400, detail="Parecer em processamento. Aguarde.")

    # Lê o Excel em memória
    raw_bytes = await arquivo.read()
    try:
        wb = load_workbook(io.BytesIO(raw_bytes), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Arquivo Excel invalido ou corrompido.")

    ws = wb.active

    # Carrega todos os itens do parecer indexados por UUID para lookup O(1)
    itens_result = await db.execute(
        select(ItemParecer).where(ItemParecer.parecer_id == parecer_id)
    )
    itens_por_id: dict[str, ItemParecer] = {
        str(i.id): i for i in itens_result.scalars().all()
    }

    # Carrega a última rodada de cada item para obter a pendência (acao_requerida)
    rodadas_result = await db.execute(
        select(RodadaAvaliacao)
        .where(RodadaAvaliacao.item_id.in_([uuid.UUID(k) for k in itens_por_id]))
        .order_by(RodadaAvaliacao.numero_rodada)
    )
    ultima_rodada_por_item: dict[str, RodadaAvaliacao] = {}
    for rodada in rodadas_result.scalars().all():
        ultima_rodada_por_item[str(rodada.item_id)] = rodada

    now = datetime.utcnow()
    processados: list[ItemProcessado] = []
    ignorados: list[ItemIgnorado] = []

    for row_num in range(_DATA_START_ROW, ws.max_row + 1):
        resposta_cell = ws.cell(row=row_num, column=_COL_RESPOSTA)
        item_id_cell = ws.cell(row=row_num, column=_COL_ITEM_ID)

        resposta_raw = resposta_cell.value
        item_id_raw = str(item_id_cell.value).strip() if item_id_cell.value else None

        # Linha vazia — ignora silenciosamente
        if not item_id_raw and not resposta_raw:
            continue

        # ITEM_ID ausente ou inválido → resolução manual
        if not item_id_raw:
            ignorados.append(ItemIgnorado(
                linha=row_num,
                motivo="ITEM_ID ausente. Nao e possivel determinar o item correspondente.",
                item_id_raw=None,
            ))
            continue

        try:
            uuid.UUID(item_id_raw)
        except ValueError:
            ignorados.append(ItemIgnorado(
                linha=row_num,
                motivo=f"ITEM_ID invalido (nao e UUID): '{item_id_raw}'",
                item_id_raw=item_id_raw,
            ))
            continue

        if item_id_raw not in itens_por_id:
            ignorados.append(ItemIgnorado(
                linha=row_num,
                motivo=f"ITEM_ID nao pertence a este parecer: '{item_id_raw}'",
                item_id_raw=item_id_raw,
            ))
            continue

        item = itens_por_id[item_id_raw]

        # Resposta em branco → sem ação
        resposta = str(resposta_raw).strip() if resposta_raw else ""
        if not resposta:
            ignorados.append(ItemIgnorado(
                linha=row_num,
                motivo="Resposta em branco. Item nao processado.",
                item_id_raw=item_id_raw,
            ))
            continue

        # Item não está aguardando resposta → alerta, mas processa mesmo assim
        if item.estado != PENDENTE_FORNECEDOR:
            ignorados.append(ItemIgnorado(
                linha=row_num,
                motivo=(
                    f"Item {item.numero} esta em estado '{item.estado}', nao em "
                    f"PENDENTE_FORNECEDOR. Resposta ignorada para evitar inconsistencia."
                ),
                item_id_raw=item_id_raw,
            ))
            continue

        # Determina o número da nova rodada
        ultima_rodada = ultima_rodada_por_item.get(item_id_raw)
        nova_rodada_num = (ultima_rodada.numero_rodada + 1) if ultima_rodada else 2

        # Pendência da rodada anterior (fallback: campo direto do item)
        pendencia = ""
        if ultima_rodada and ultima_rodada.acao_requerida:
            pendencia = ultima_rodada.acao_requerida
        elif item.acao_requerida:
            pendencia = item.acao_requerida
        else:
            pendencia = item.descricao_requisito or ""

        # Chama o Agente Avaliador (síncrono → thread)
        evaluation = await asyncio.to_thread(
            avaliar_resposta,
            item.descricao_requisito or "",
            pendencia,
            resposta,
        )

        # Cria a nova RodadaAvaliacao (append-only)
        nova_rodada = RodadaAvaliacao(
            id=uuid.uuid4(),
            item_id=item.id,
            numero_rodada=nova_rodada_num,
            origem="RESPOSTA_FORNECEDOR",
            conteudo=resposta,
            veredito_ia=evaluation.veredito,
            justificativa_ia=evaluation.justificativa,
            acao_requerida=evaluation.acao_requerida,
            criado_em=now,
        )
        db.add(nova_rodada)

        # Transiciona o estado do item para EM_REAVALIACAO
        item.estado = transicionar(item.estado, "fornecedor_respondeu")

        processados.append(ItemProcessado(
            item_id=item_id_raw,
            numero=item.numero,
            veredito_ia=evaluation.veredito,
            justificativa_ia=evaluation.justificativa,
            acao_requerida=evaluation.acao_requerida,
        ))

        logger.info(
            "Reimport: parecer=%s item=%s rodada=%d veredito=%s",
            parecer_id, item_id_raw, nova_rodada_num, evaluation.veredito,
        )

    # Atualiza o estado global do parecer
    if processados:
        todos_estados_result = await db.execute(
            select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
        )
        todos_estados = [row[0] for row in todos_estados_result.all()]
        parecer.status_global = compute_status_global(todos_estados)

        # Incrementa rodada_atual apenas se houve processamento real
        parecer.rodada_atual = (getattr(parecer, "rodada_atual", 1) or 1) + 1

    await db.commit()

    n_proc = len(processados)
    n_ign = len(ignorados)
    mensagem = (
        f"{n_proc} item(ns) processado(s) com sucesso. "
        f"{n_ign} ignorado(s) (ver campo 'ignorados' para detalhes)."
    )
    if n_proc == 0:
        mensagem = "Nenhum item foi processado. Verifique se o arquivo esta correto e as respostas preenchidas."

    return ReimportResult(
        processados=processados,
        ignorados=ignorados,
        total_processados=n_proc,
        total_ignorados=n_ign,
        mensagem=mensagem,
    )
