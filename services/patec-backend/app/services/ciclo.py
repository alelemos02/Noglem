"""
Serviço do ciclo com o fornecedor — rodadas tipos 1-4, vinculação (W3) e
avaliação das respostas (R2).

Fluxo de uma rodada (blocos 21-24 do fluxo do caso técnico):
  1. criar_rodada            — engenheiro carrega o material informando o tipo
  2. run_vinculacao_sync     — (Celery) LLM sugere vínculos; nada muda de estado
  3. confirmar_vinculacao    — W3: engenheiro valida; itens transicionam
  4. run_avaliacao_sync      — (Celery) R2: LLM avalia cada resposta vinculada

O BD central só registra o que foi validado por humano: os vínculos sugeridos
ficam provisórios (sem transição de estado) até a confirmação.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - ensure all model mappers are registered
from app.core.config import settings
from app.core.progress import set_progress
from app.models.item_parecer import ItemParecer
from app.models.rodada_avaliacao import RodadaAvaliacao
from app.models.rodada_fornecedor import (
    TIPO_PROPOSTA_REVISADA,
    RodadaFornecedor,
)
from app.services.evaluator import avaliar_resposta
from app.services.state_machine import PENDENTE_FORNECEDOR
from app.services.vinculador import vincular_proposta_revisada, vincular_respostas_llm

logger = logging.getLogger(__name__)

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def _progress_key(rodada_id: str) -> str:
    return f"rodada:{rodada_id}"


def _texto_da_rodada(rodada: RodadaFornecedor) -> str:
    if rodada.texto_colado and rodada.texto_colado.strip():
        return rodada.texto_colado
    if rodada.documento is not None and rodada.documento.texto_extraido:
        return rodada.documento.texto_extraido
    raise ValueError("Rodada sem material: nem texto colado nem documento com texto extraido.")


def _serializar_historico(rodadas: list[RodadaAvaliacao]) -> str:
    """R2: serializa as rodadas anteriores do item para o prompt do avaliador."""
    linhas = []
    for r in rodadas:
        partes = [f"Rodada {r.numero_rodada} ({r.origem})"]
        if r.classificacao_ia:
            partes.append(f"classificacao={r.classificacao_ia}")
        if r.veredito_ia:
            partes.append(f"veredito LLM={r.veredito_ia}")
        if r.decisao_humana:
            partes.append(f"decisao do engenheiro={r.decisao_humana}")
        linhas.append(" | ".join(partes))
        if r.conteudo:
            linhas.append(f"  Conteudo: {r.conteudo[:400]}")
        if r.acao_requerida:
            linhas.append(f"  Acao requerida: {r.acao_requerida[:300]}")
    return "\n".join(linhas)


# ──────────────────────────────────────────────────────── corpo das tasks ──

def run_vinculacao_sync(rodada_id: str) -> dict:
    """
    Corpo da task Celery: LLM sugere vínculos entre a resposta do fornecedor e
    os itens abertos (PENDENTE_FORNECEDOR). Cria RodadaAvaliacao provisórias —
    sem transição de estado (isso só acontece na confirmação humana, W3).
    """
    key = _progress_key(rodada_id)
    set_progress(key, 10, "Carregando rodada e itens abertos...", "loading")
    engine = _get_sync_engine()

    try:
        with Session(engine) as db:
            rodada = db.execute(
                select(RodadaFornecedor).where(RodadaFornecedor.id == uuid.UUID(rodada_id))
            ).scalar_one_or_none()
            if not rodada:
                set_progress(key, 100, "Rodada nao encontrada", "error")
                return {"error": "Rodada nao encontrada"}

            itens = db.execute(
                select(ItemParecer)
                .where(
                    ItemParecer.parecer_id == rodada.parecer_id,
                    ItemParecer.estado == PENDENTE_FORNECEDOR,
                )
                .order_by(ItemParecer.numero)
            ).scalars().all()

            if not itens:
                rodada.status = "ERRO"
                rodada.erro_detalhe = "Nenhum item aguardando resposta do fornecedor."
                db.commit()
                set_progress(key, 100, rodada.erro_detalhe, "error")
                return {"error": rodada.erro_detalhe}

            # Última rodada de cada item fornece a pendência exibida na vinculação
            ultima_acao: dict[int, str | None] = {}
            for item in itens:
                ultima = db.execute(
                    select(RodadaAvaliacao)
                    .where(RodadaAvaliacao.item_id == item.id)
                    .order_by(RodadaAvaliacao.numero_rodada.desc())
                    .limit(1)
                ).scalar_one_or_none()
                ultima_acao[item.numero] = (
                    (ultima.acao_requerida if ultima else None) or item.acao_requerida
                )

            itens_payload = [
                {
                    "numero": i.numero,
                    "descricao_requisito": i.descricao_requisito,
                    "valor_requerido": i.valor_requerido,
                    "pendencia": ultima_acao.get(i.numero),
                }
                for i in itens
            ]

            if rodada.tipo == TIPO_PROPOSTA_REVISADA:
                set_progress(key, 50, "Proposta revisada: vinculando todos os itens abertos...", "linking")
                resultado = vincular_proposta_revisada(itens_payload)
                metodo = "DETERMINISTICO"
            else:
                texto = _texto_da_rodada(rodada)
                set_progress(key, 40, "LLM vinculando respostas aos itens...", "llm_linking")
                resultado = vincular_respostas_llm(texto, itens_payload, rodada.tipo)
                metodo = "LLM"

            set_progress(key, 80, "Registrando vinculos sugeridos...", "saving")
            item_por_numero = {i.numero: i for i in itens}
            now = datetime.utcnow()

            for vinculo in resultado["vinculos"]:
                item = item_por_numero[vinculo["item_numero"]]
                proxima = db.execute(
                    select(func.max(RodadaAvaliacao.numero_rodada)).where(
                        RodadaAvaliacao.item_id == item.id
                    )
                ).scalar() or 0
                db.add(
                    RodadaAvaliacao(
                        item_id=item.id,
                        rodada_fornecedor_id=rodada.id,
                        numero_rodada=proxima + 1,
                        origem="RESPOSTA_FORNECEDOR",
                        conteudo=vinculo["trecho"],
                        trecho_vinculado=vinculo["trecho"],
                        vinculo_confianca=vinculo["confianca"],
                        vinculo_metodo=metodo,
                        criado_em=now,
                    )
                )

            rodada.status = "VINCULACAO_SUGERIDA"
            db.commit()

            n = len(resultado["vinculos"])
            set_progress(
                key, 100,
                f"{n} vinculo(s) sugerido(s). Revise e confirme a vinculacao.",
                "completed",
            )
            return {
                "status": "VINCULACAO_SUGERIDA",
                "vinculos": n,
                "itens_sem_resposta": resultado["itens_sem_resposta"],
            }
    except Exception as e:
        logger.exception("Vinculacao falhou para rodada %s", rodada_id)
        msg = str(e)[:500]
        set_progress(key, 100, f"Erro na vinculacao: {msg}", "error")
        try:
            with Session(_get_sync_engine()) as db:
                rodada = db.execute(
                    select(RodadaFornecedor).where(RodadaFornecedor.id == uuid.UUID(rodada_id))
                ).scalar_one_or_none()
                if rodada:
                    rodada.status = "ERRO"
                    rodada.erro_detalhe = msg
                    db.commit()
        except Exception:
            logger.exception("Falha ao persistir erro da rodada %s", rodada_id)
        return {"error": msg}


def run_avaliacao_sync(rodada_id: str) -> dict:
    """
    Corpo da task Celery (R2): após a confirmação humana (W3), avalia cada
    resposta vinculada contra a pendência e o histórico de acordos do item.
    """
    key = _progress_key(rodada_id)
    set_progress(key, 10, "Carregando vinculos confirmados...", "loading")
    engine = _get_sync_engine()

    try:
        with Session(engine) as db:
            rodada = db.execute(
                select(RodadaFornecedor).where(RodadaFornecedor.id == uuid.UUID(rodada_id))
            ).scalar_one_or_none()
            if not rodada:
                set_progress(key, 100, "Rodada nao encontrada", "error")
                return {"error": "Rodada nao encontrada"}

            avaliacoes = db.execute(
                select(RodadaAvaliacao).where(
                    RodadaAvaliacao.rodada_fornecedor_id == rodada.id
                )
            ).scalars().all()

            texto_proposta = None
            if rodada.tipo == TIPO_PROPOSTA_REVISADA:
                texto_proposta = _texto_da_rodada(rodada)

            total = len(avaliacoes)
            for idx, avaliacao in enumerate(avaliacoes, start=1):
                item = db.execute(
                    select(ItemParecer).where(ItemParecer.id == avaliacao.item_id)
                ).scalar_one()

                anteriores = db.execute(
                    select(RodadaAvaliacao)
                    .where(
                        RodadaAvaliacao.item_id == item.id,
                        RodadaAvaliacao.numero_rodada < avaliacao.numero_rodada,
                    )
                    .order_by(RodadaAvaliacao.numero_rodada)
                ).scalars().all()

                pendencia = ""
                if anteriores and anteriores[-1].acao_requerida:
                    pendencia = anteriores[-1].acao_requerida
                elif item.acao_requerida:
                    pendencia = item.acao_requerida

                resposta = avaliacao.trecho_vinculado or texto_proposta or ""
                if not resposta.strip():
                    continue

                set_progress(
                    key,
                    10 + int(80 * idx / max(total, 1)),
                    f"Avaliando resposta do item {item.numero} ({idx}/{total})...",
                    "llm_evaluating",
                )
                resultado = avaliar_resposta(
                    item.descricao_requisito or "",
                    pendencia,
                    resposta,
                    historico_acordos=_serializar_historico(anteriores),
                )
                avaliacao.veredito_ia = resultado.veredito
                avaliacao.justificativa_ia = resultado.justificativa
                avaliacao.acao_requerida = resultado.acao_requerida
                db.commit()

            rodada.status = "AVALIADA"
            db.commit()
            set_progress(
                key, 100,
                f"{total} resposta(s) avaliada(s). Itens prontos para sua decisao.",
                "completed",
            )
            return {"status": "AVALIADA", "avaliadas": total}
    except Exception as e:
        logger.exception("Avaliacao falhou para rodada %s", rodada_id)
        msg = str(e)[:500]
        set_progress(key, 100, f"Erro na avaliacao: {msg}", "error")
        return {"error": msg}


def start_vinculacao_in_background(rodada_id: str) -> str:
    """Enfileira a vinculação (bloco 23) no Celery e devolve o task id."""
    from app.worker import processar_vinculacao_task

    task = processar_vinculacao_task.delay(rodada_id)
    return task.id


def start_avaliacao_in_background(rodada_id: str) -> str:
    """Enfileira a avaliação R2 (bloco 24) no Celery e devolve o task id."""
    from app.worker import avaliar_rodada_task

    task = avaliar_rodada_task.delay(rodada_id)
    return task.id
