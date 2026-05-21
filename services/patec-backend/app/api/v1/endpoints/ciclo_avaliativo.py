"""
Endpoints do ciclo iterativo de avaliação de pareceres técnicos.

GET  /{parecer_id}/exportar/carta-pendencias
POST /{parecer_id}/reimportar-respostas
GET  /{parecer_id}/ciclo/resumo
GET  /{parecer_id}/ciclo/reavaliacao
POST /{parecer_id}/ciclo/itens/{item_id}/decidir
POST /{parecer_id}/ciclo/itens/{item_id}/escalonar
GET  /{parecer_id}/ciclo/itens/{item_id}/historico
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
    ABERTO,
    ESCALONADO,
    PENDENTE_FORNECEDOR,
    EM_REAVALIACAO,
    RESOLVIDO,
    TransicaoInvalidaError,
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


# ──────────────────────────────────────────────────────────────────────────────
# Fase 3 — Validação humana e fechamento do ciclo
# ──────────────────────────────────────────────────────────────────────────────

class EstadoCount(BaseModel):
    estado: str
    total: int


class CicloResumoResponse(BaseModel):
    status_global: str
    rodada_atual: int
    contagem_por_estado: list[EstadoCount]
    total_itens: int
    tem_pendentes: bool
    tem_em_reavaliacao: bool


class RodadaResponse(BaseModel):
    id: str
    numero_rodada: int
    origem: str
    conteudo: str | None
    anexo_ref: str | None
    classificacao_ia: str | None
    veredito_ia: str | None
    justificativa_ia: str | None
    acao_requerida: str | None
    decisao_humana: str | None
    revisor: str | None
    criado_em: str


class ItemRevisaoResponse(BaseModel):
    id: str
    numero: int
    categoria: str | None
    descricao_requisito: str
    valor_requerido: str | None
    prioridade: str | None
    estado: str
    ultima_rodada: RodadaResponse | None


def _rodada_to_response(r: RodadaAvaliacao) -> RodadaResponse:
    return RodadaResponse(
        id=str(r.id),
        numero_rodada=r.numero_rodada,
        origem=r.origem,
        conteudo=r.conteudo,
        anexo_ref=r.anexo_ref,
        classificacao_ia=r.classificacao_ia,
        veredito_ia=r.veredito_ia,
        justificativa_ia=r.justificativa_ia,
        acao_requerida=r.acao_requerida,
        decisao_humana=r.decisao_humana,
        revisor=r.revisor,
        criado_em=r.criado_em.isoformat(),
    )


@router.get("/{parecer_id}/ciclo/resumo", response_model=CicloResumoResponse)
async def ciclo_resumo(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")

    estados_result = await db.execute(
        select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
    )
    todos_estados = [row[0] for row in estados_result.all()]

    from collections import Counter
    counts = Counter(todos_estados)
    contagem = [
        EstadoCount(estado=estado, total=total)
        for estado, total in sorted(counts.items())
    ]

    return CicloResumoResponse(
        status_global=getattr(parecer, "status_global", "EM_ANALISE"),
        rodada_atual=getattr(parecer, "rodada_atual", 1),
        contagem_por_estado=contagem,
        total_itens=len(todos_estados),
        tem_pendentes=counts.get(PENDENTE_FORNECEDOR, 0) > 0,
        tem_em_reavaliacao=counts.get(EM_REAVALIACAO, 0) > 0,
    )


@router.get("/{parecer_id}/ciclo/reavaliacao", response_model=list[ItemRevisaoResponse])
async def itens_em_reavaliacao(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    itens_result = await db.execute(
        select(ItemParecer)
        .where(
            ItemParecer.parecer_id == parecer_id,
            ItemParecer.estado == EM_REAVALIACAO,
        )
        .order_by(ItemParecer.numero)
    )
    itens = itens_result.scalars().all()

    if not itens:
        return []

    item_ids = [i.id for i in itens]
    rodadas_result = await db.execute(
        select(RodadaAvaliacao)
        .where(RodadaAvaliacao.item_id.in_(item_ids))
        .order_by(RodadaAvaliacao.numero_rodada)
    )
    ultimas: dict[str, RodadaAvaliacao] = {}
    for r in rodadas_result.scalars().all():
        ultimas[str(r.item_id)] = r

    return [
        ItemRevisaoResponse(
            id=str(i.id),
            numero=i.numero,
            categoria=i.categoria,
            descricao_requisito=i.descricao_requisito,
            valor_requerido=i.valor_requerido,
            prioridade=i.prioridade,
            estado=i.estado,
            ultima_rodada=_rodada_to_response(ultimas[str(i.id)]) if str(i.id) in ultimas else None,
        )
        for i in itens
    ]


class DecisoHumanaRequest(BaseModel):
    decisao_humana: str  # ATENDE | NAO_ATENDE | PARCIAL


class DecisoHumanaResponse(BaseModel):
    item_id: str
    numero: int
    novo_estado: str
    status_global: str
    mensagem: str


@router.post("/{parecer_id}/ciclo/itens/{item_id}/decidir", response_model=DecisoHumanaResponse)
async def decidir_item(
    parecer_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: DecisoHumanaRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin", "analista")),
):
    if payload.decisao_humana not in {"ATENDE", "NAO_ATENDE", "PARCIAL"}:
        raise HTTPException(status_code=400, detail="decisao_humana deve ser ATENDE, NAO_ATENDE ou PARCIAL.")

    item_result = await db.execute(
        select(ItemParecer).where(
            ItemParecer.id == item_id,
            ItemParecer.parecer_id == parecer_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item nao encontrado neste parecer.")
    if item.estado != EM_REAVALIACAO:
        raise HTTPException(
            status_code=400,
            detail=f"Item esta em estado '{item.estado}', nao em EM_REAVALIACAO.",
        )

    # Registra a decisão na rodada mais recente (RESPOSTA_FORNECEDOR)
    ultima_result = await db.execute(
        select(RodadaAvaliacao)
        .where(RodadaAvaliacao.item_id == item_id)
        .order_by(RodadaAvaliacao.numero_rodada.desc())
        .limit(1)
    )
    ultima_rodada = ultima_result.scalar_one_or_none()
    if ultima_rodada:
        ultima_rodada.decisao_humana = payload.decisao_humana
        revisor_id = getattr(current_user, "id", None)
        ultima_rodada.revisor = str(revisor_id) if revisor_id else None

    # Aplica transição de estado
    evento = "aceitar" if payload.decisao_humana == "ATENDE" else "rejeitar"
    item.estado = transicionar(item.estado, evento)

    # Recalcula status_global
    todos_estados_result = await db.execute(
        select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
    )
    todos_estados = [row[0] for row in todos_estados_result.all()]

    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    novo_status_global = compute_status_global(todos_estados)
    if parecer:
        parecer.status_global = novo_status_global

    await db.commit()

    return DecisoHumanaResponse(
        item_id=str(item_id),
        numero=item.numero,
        novo_estado=item.estado,
        status_global=novo_status_global,
        mensagem=(
            f"Item {item.numero} movido para {item.estado}. "
            + ("Resolucao confirmada." if item.estado == RESOLVIDO else "Aguardando nova rodada do fornecedor.")
        ),
    )


class EscalonarResponse(BaseModel):
    item_id: str
    numero: int
    novo_estado: str
    status_global: str


@router.post("/{parecer_id}/ciclo/itens/{item_id}/escalonar", response_model=EscalonarResponse)
async def escalonar_item(
    parecer_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_role("admin", "analista")),
):
    item_result = await db.execute(
        select(ItemParecer).where(
            ItemParecer.id == item_id,
            ItemParecer.parecer_id == parecer_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item nao encontrado neste parecer.")

    try:
        item.estado = transicionar(item.estado, "escalar")
    except TransicaoInvalidaError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    todos_estados_result = await db.execute(
        select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
    )
    todos_estados = [row[0] for row in todos_estados_result.all()]
    novo_status_global = compute_status_global(todos_estados)

    parecer_result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = parecer_result.scalar_one_or_none()
    if parecer:
        parecer.status_global = novo_status_global

    await db.commit()

    return EscalonarResponse(
        item_id=str(item_id),
        numero=item.numero,
        novo_estado=item.estado,
        status_global=novo_status_global,
    )


@router.get("/{parecer_id}/ciclo/itens/{item_id}/historico", response_model=list[RodadaResponse])
async def historico_item(
    parecer_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    item_result = await db.execute(
        select(ItemParecer).where(
            ItemParecer.id == item_id,
            ItemParecer.parecer_id == parecer_id,
        )
    )
    if not item_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Item nao encontrado neste parecer.")

    rodadas_result = await db.execute(
        select(RodadaAvaliacao)
        .where(RodadaAvaliacao.item_id == item_id)
        .order_by(RodadaAvaliacao.numero_rodada)
    )
    return [_rodada_to_response(r) for r in rodadas_result.scalars().all()]
