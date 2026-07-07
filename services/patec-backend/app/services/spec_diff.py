"""
Revisão da especificação — caminho lateral do caso técnico (blocos 35-41).

- R4 (run_spec_diff_sync, Celery): a LLM compara a nova revisão do documento
  de engenharia contra os requisitos ativos do BD e classifica o cenário.
- W7 (aplicar_revisao): aplica o diff validado pelo engenheiro:
    alterados  → requisito atualizado (versao+1), item reaberto e devolvido ao
                 fornecedor com marcação ALTERADO; histórico preservado em rodada
                 origem=REVISAO_SPEC; classificação prévia perde validade.
    removidos  → requisito desativado (nunca apagado) e item DESATIVADO.
    novos      → requisito criado (origem na revisão) + item novo com marcação
                 NOVO, já como pendência para o fornecedor.
  Cenário A retorna ao ponto onde estava; B pergunta ao engenheiro quais novos
  incluir (bloco 40); C força a atualização. B/C regridem o caso para
  CICLO_FORNECEDOR (bloco 41 → 18: novo parecer com highlight vai ao fornecedor).
"""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - ensure all model mappers are registered
from app.core.config import settings
from app.core.progress import set_progress
from app.models.documento import Documento
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.requisito import Requisito
from app.models.rodada_avaliacao import RodadaAvaliacao
from app.models.versao_especificacao import VersaoEspecificacao
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.spec_diff import (
    SPEC_DIFF_SYSTEM_PROMPT,
    SPEC_DIFF_USER_TEMPLATE,
)
from app.services.state_machine import transicionar

logger = logging.getLogger(__name__)

_sync_engine = None

_CAMPOS_ALTERAVEIS = {
    "descricao_requisito",
    "valor_requerido",
    "categoria",
    "prioridade",
    "norma_referencia",
    "referencia_engenharia",
}


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def _progress_key(versao_id: str) -> str:
    return f"specdiff:{versao_id}"


def _derivar_cenario(diff: dict) -> str:
    if diff["alterados"] or diff["removidos"]:
        return "C"
    if diff["novos"]:
        return "B"
    return "A"


def normalizar_diff(data: dict, numeros_validos: set[int]) -> dict:
    """Valida e normaliza a saída da LLM; o cenário é re-derivado localmente."""
    alterados = []
    for a in data.get("alterados", []):
        numero = a.get("numero")
        if numero not in numeros_validos:
            continue
        campos = {
            campo: {
                "antes": str(mudanca.get("antes", "")),
                "depois": str(mudanca.get("depois", "")),
            }
            for campo, mudanca in (a.get("campos_alterados") or {}).items()
            if campo in _CAMPOS_ALTERAVEIS and isinstance(mudanca, dict)
        }
        if not campos:
            continue
        alterados.append({
            "numero": numero,
            "campos_alterados": campos,
            "justificativa": str(a.get("justificativa", "")).strip(),
        })

    numeros_alterados = {a["numero"] for a in alterados}
    removidos = [
        n for n in data.get("removidos", [])
        if n in numeros_validos and n not in numeros_alterados
    ]

    novos = []
    valid_prios = {"ALTA", "MEDIA", "BAIXA"}
    for n in data.get("novos", []):
        descricao = str(n.get("descricao_requisito", "")).strip()
        if not descricao:
            continue
        prioridade = str(n.get("prioridade", "")).upper()
        novos.append({
            "categoria": n.get("categoria"),
            "descricao_requisito": descricao,
            "valor_requerido": n.get("valor_requerido"),
            "prioridade": prioridade if prioridade in valid_prios else "MEDIA",
            "norma_referencia": n.get("norma_referencia"),
            "referencia_engenharia": n.get("referencia_engenharia") or "",
        })

    inalterados = sorted(
        numeros_validos - numeros_alterados - set(removidos)
    )

    diff = {
        "inalterados": inalterados,
        "alterados": alterados,
        "novos": novos,
        "removidos": sorted(removidos),
        "resumo": str(data.get("resumo", "")).strip(),
    }
    diff["cenario"] = _derivar_cenario(diff)
    return diff


def run_spec_diff_sync(versao_id: str) -> dict:
    """Corpo da task Celery (R4): compara a nova revisão contra os requisitos do BD."""
    key = _progress_key(versao_id)
    engine = _get_sync_engine()

    try:
        with Session(engine) as db:
            versao = db.execute(
                select(VersaoEspecificacao).where(
                    VersaoEspecificacao.id == uuid.UUID(versao_id)
                )
            ).scalar_one_or_none()
            if not versao:
                return {"error": "Versao nao encontrada"}

            set_progress(key, 10, "Carregando nova revisao e requisitos atuais...", "loading")

            documento = db.execute(
                select(Documento).where(Documento.id == versao.documento_id)
            ).scalar_one_or_none()
            if not documento or not documento.texto_extraido:
                raise ValueError("Documento da nova revisao sem texto extraido.")

            requisitos = db.execute(
                select(Requisito)
                .where(
                    Requisito.parecer_id == versao.parecer_id,
                    Requisito.ativo.is_(True),
                    Requisito.aprovado_em.isnot(None),
                )
                .order_by(Requisito.numero)
            ).scalars().all()
            if not requisitos:
                raise ValueError("Caso sem requisitos ativos para comparar.")

            requisitos_payload = [
                {
                    "numero": r.numero,
                    "categoria": r.categoria,
                    "descricao_requisito": r.descricao_requisito,
                    "valor_requerido": r.valor_requerido,
                    "prioridade": r.prioridade,
                    "norma_referencia": r.norma_referencia,
                    "referencia_engenharia": r.referencia_engenharia,
                }
                for r in requisitos
            ]

            set_progress(key, 40, "LLM comparando revisao contra requisitos do caso...", "llm_diffing")
            user_content = SPEC_DIFF_USER_TEMPLATE.format(
                texto_nova_revisao=documento.texto_extraido,
                requisitos_json=json.dumps(requisitos_payload, ensure_ascii=False, indent=2),
            )
            raw = call_llm(SPEC_DIFF_SYSTEM_PROMPT, user_content)
            data = extract_json(raw)

            diff = normalizar_diff(data, {r.numero for r in requisitos})
            versao.resumo_diff = diff
            versao.cenario = diff["cenario"]

            if diff["cenario"] == "A":
                # Cenário A: nada mudou — fluxo retorna ao ponto onde estava
                versao.status = "APLICADA"
                versao.aplicado_em = datetime.utcnow()
                parecer = db.execute(
                    select(Parecer).where(Parecer.id == versao.parecer_id)
                ).scalar_one()
                parecer.revisao_spec_em_andamento = False
                mensagem = (
                    "Nenhuma mudanca tecnica detectada — o caso continua de onde estava."
                )
            else:
                versao.status = "AGUARDANDO_DECISAO"
                mensagem = (
                    f"Cenario {diff['cenario']}: {len(diff['alterados'])} alterado(s), "
                    f"{len(diff['novos'])} novo(s), {len(diff['removidos'])} removido(s). "
                    "Revise e aplique a revisao."
                )

            db.commit()
            set_progress(key, 100, mensagem, "completed")

            # Diff concluido: agora (sem concorrer com a LLM da comparacao) e
            # seguro indexar a nova revisao para o RAG do chat. A indexacao foi
            # adiada no upload justamente para nao estourar 429 durante o diff.
            try:
                from app.services.indexer import enqueue_indexing

                enqueue_indexing(str(versao.documento_id))
            except Exception:
                logger.exception(
                    "Falha ao enfileirar indexacao da revisao %s", versao_id
                )

            return {"status": versao.status, "cenario": diff["cenario"]}
    except Exception as e:
        logger.exception("Spec diff falhou para versao %s", versao_id)
        msg = str(e)[:500]
        set_progress(key, 100, f"Erro na comparacao: {msg}", "error")
        try:
            with Session(_get_sync_engine()) as db:
                versao = db.execute(
                    select(VersaoEspecificacao).where(
                        VersaoEspecificacao.id == uuid.UUID(versao_id)
                    )
                ).scalar_one_or_none()
                if versao:
                    versao.status = "ERRO"
                    versao.erro_detalhe = msg
                    parecer = db.execute(
                        select(Parecer).where(Parecer.id == versao.parecer_id)
                    ).scalar_one_or_none()
                    if parecer:
                        parecer.revisao_spec_em_andamento = False
                    db.commit()
        except Exception:
            logger.exception("Falha ao persistir erro da versao %s", versao_id)
        return {"error": msg}


def aplicar_revisao_sync(
    db: Session,
    versao: VersaoEspecificacao,
    incluir_novos: list[int],
    usuario_id,
) -> dict:
    """
    Operação W7 (síncrona, chamada pelo endpoint via run_sync ou sessão sync):
    aplica o diff validado. `incluir_novos` são os índices (0-based) dos itens
    novos aceitos pelo engenheiro (bloco 40); no cenário C os alterados e
    removidos são aplicados obrigatoriamente.
    """
    diff = versao.resumo_diff or {}
    parecer = db.execute(
        select(Parecer).where(Parecer.id == versao.parecer_id)
    ).scalar_one()

    requisitos = db.execute(
        select(Requisito).where(
            Requisito.parecer_id == versao.parecer_id,
            Requisito.ativo.is_(True),
        )
    ).scalars().all()
    req_por_numero = {r.numero: r for r in requisitos}

    itens = db.execute(
        select(ItemParecer).where(ItemParecer.parecer_id == versao.parecer_id)
    ).scalars().all()
    item_por_requisito = {i.requisito_id: i for i in itens if i.requisito_id}
    max_item_numero = max((i.numero for i in itens), default=0)
    max_req_numero = max((r.numero for r in requisitos), default=0)

    now = datetime.utcnow()
    rev_label = f"REV-{versao.numero_versao}"
    reabertos = 0
    desativados = 0
    incluidos = 0

    def _registrar_rodada(item: ItemParecer, conteudo: str):
        proxima = db.execute(
            select(func.max(RodadaAvaliacao.numero_rodada)).where(
                RodadaAvaliacao.item_id == item.id
            )
        ).scalar() or 0
        db.add(
            RodadaAvaliacao(
                item_id=item.id,
                numero_rodada=proxima + 1,
                origem="REVISAO_SPEC",
                conteudo=conteudo,
                criado_em=now,
            )
        )

    # Itens ALTERADOS: requisito atualizado; item reabre como novo (perde a
    # classificação prévia) e volta como pendência ao fornecedor.
    for alterado in diff.get("alterados", []):
        requisito = req_por_numero.get(alterado["numero"])
        if not requisito:
            continue
        mudancas_txt = []
        for campo, mudanca in alterado["campos_alterados"].items():
            setattr(requisito, campo, mudanca["depois"] or None)
            mudancas_txt.append(f"{campo}: '{mudanca['antes']}' -> '{mudanca['depois']}'")
        requisito.versao += 1
        requisito.alterado_versao_spec_id = versao.id

        item = item_por_requisito.get(requisito.id)
        if item:
            # Reabre preservando o histórico nas rodadas; classificação prévia
            # perde validade (mesmo itens já aceitos).
            transicionar(item.estado, "reabrir_revisao_spec")  # valida a transição
            item.estado = "PENDENTE_FORNECEDOR"
            item.marcacao_revisao = "ALTERADO"
            item.status = "D"
            item.descricao_requisito = requisito.descricao_requisito
            item.valor_requerido = requisito.valor_requerido
            item.categoria = requisito.categoria
            item.prioridade = requisito.prioridade
            item.norma_referencia = requisito.norma_referencia
            item.referencia_engenharia = requisito.referencia_engenharia
            item.justificativa_tecnica = (
                f"Requisito alterado pela revisao de especificacao {rev_label}. "
                "Classificacao anterior invalidada; aguarda resposta do fornecedor."
            )
            item.acao_requerida = (
                "Atender ao requisito conforme a nova revisao da especificacao."
            )
            _registrar_rodada(
                item,
                f"[{rev_label}] Requisito alterado ({alterado.get('justificativa', '')}). "
                + "; ".join(mudancas_txt),
            )
            reabertos += 1

    # Itens REMOVIDOS: desativados, nunca apagados (rastreabilidade total)
    for numero in diff.get("removidos", []):
        requisito = req_por_numero.get(numero)
        if not requisito:
            continue
        requisito.ativo = False
        requisito.desativado_em = now
        requisito.desativado_motivo = f"Removido pela revisao de especificacao {rev_label}."
        item = item_por_requisito.get(requisito.id)
        if item:
            item.estado = transicionar(item.estado, "desativar")
            item.marcacao_revisao = None
            _registrar_rodada(
                item, f"[{rev_label}] Requisito removido da especificacao — item desativado."
            )
            desativados += 1

    # Itens NOVOS aceitos pelo engenheiro (bloco 40 / cenário C)
    novos = diff.get("novos", [])
    for idx in incluir_novos:
        if idx < 0 or idx >= len(novos):
            continue
        novo = novos[idx]
        max_req_numero += 1
        max_item_numero += 1
        requisito = Requisito(
            parecer_id=versao.parecer_id,
            numero=max_req_numero,
            categoria=novo.get("categoria"),
            descricao_requisito=novo["descricao_requisito"],
            referencia_engenharia=novo.get("referencia_engenharia"),
            valor_requerido=novo.get("valor_requerido"),
            prioridade=novo.get("prioridade") or "MEDIA",
            norma_referencia=novo.get("norma_referencia"),
            origem_versao_spec_id=versao.id,
            aprovado_por=usuario_id,
            aprovado_em=now,
        )
        db.add(requisito)
        db.flush()
        item = ItemParecer(
            parecer_id=versao.parecer_id,
            requisito_id=requisito.id,
            numero=max_item_numero,
            categoria=requisito.categoria,
            descricao_requisito=requisito.descricao_requisito,
            referencia_engenharia=requisito.referencia_engenharia,
            valor_requerido=requisito.valor_requerido,
            status="D",
            justificativa_tecnica=(
                f"Item incluido pela revisao de especificacao {rev_label}; "
                "aguarda resposta do fornecedor."
            ),
            acao_requerida="Apresentar atendimento ao novo requisito da especificacao.",
            prioridade=requisito.prioridade,
            norma_referencia=requisito.norma_referencia,
            estado="PENDENTE_FORNECEDOR",
            marcacao_revisao="NOVO",
        )
        db.add(item)
        db.flush()
        _registrar_rodada(item, f"[{rev_label}] Item incluido pela revisao da especificacao.")
        incluidos += 1

    # Fechamento da operação W7
    versao.status = "APLICADA"
    versao.aplicado_por = usuario_id
    versao.aplicado_em = now
    parecer.revisao_spec_em_andamento = False

    houve_mudanca = bool(reabertos or desativados or incluidos)
    if houve_mudanca:
        # Bloco 41 → 18: o caso regride para o ciclo com o fornecedor
        parecer.fase_caso = "CICLO_FORNECEDOR"
        parecer.total_itens = (parecer.total_itens or 0) + incluidos

    return {
        "cenario": versao.cenario,
        "reabertos": reabertos,
        "desativados": desativados,
        "incluidos": incluidos,
        "fase_caso": parecer.fase_caso,
    }


def start_spec_diff_in_background(versao_id: str) -> str:
    """Enfileira a comparação R4 no Celery e devolve o task id."""
    from app.worker import comparar_spec_task

    task = comparar_spec_task.delay(versao_id)
    return task.id
