"""
Verificador final do caso (blocos 29-33 do fluxo).

- Bifurcação (bloco 29): se a última rodada decidida veio do Tipo 1 (proposta
  totalmente revisada), a verificação LLM é dispensada — a proposta já foi
  analisada nas rodadas. Casos 100% aprovados na análise inicial também
  dispensam (não houve ciclo).
- R3: a LLM compara a proposta final contra requisitos + acordos do BD central.
- W5: o engenheiro valida o resultado — só então o fechamento (W6) é liberado.
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
from app.models.item_parecer import ItemParecer
from app.models.rodada_avaliacao import RodadaAvaliacao
from app.models.rodada_fornecedor import TIPO_PROPOSTA_REVISADA, RodadaFornecedor
from app.models.verificacao_final import VerificacaoFinal
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.verificacao import (
    VERIFICACAO_SYSTEM_PROMPT,
    VERIFICACAO_USER_TEMPLATE,
)
from app.services.state_machine import DESATIVADO

logger = logging.getLogger(__name__)

_sync_engine = None

_VALID_CONFORMIDADES = {"CONFORME", "PARCIAL", "NAO_CONFORME"}

# Conformidade da verificação → veredito aceito pelo CHECK de rodadas_avaliacao
_CONFORMIDADE_PARA_VEREDITO = {
    "CONFORME": "ATENDE",
    "PARCIAL": "PARCIAL",
    "NAO_CONFORME": "NAO_ATENDE",
}


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def _progress_key(parecer_id: str) -> str:
    return f"verificacao:{parecer_id}"


def calcular_bifurcacao(db, parecer_id) -> bool:
    """
    Bloco 29: devolve True quando a verificação LLM é dispensada.

    Dispensada quando a última rodada do fornecedor que gerou decisões foi do
    Tipo 1 (a LLM acabou de analisar a proposta revisada — reanalisar seria
    redundante) ou quando não houve nenhuma rodada (caso 100% aprovado na
    análise inicial). Funciona com Session sync e AsyncSession (via run_sync).
    """
    ultima_tipo = db.execute(
        select(RodadaFornecedor.tipo)
        .where(
            RodadaFornecedor.parecer_id == parecer_id,
            RodadaFornecedor.proposta_final.is_(False),
        )
        .order_by(RodadaFornecedor.numero.desc())
        .limit(1)
    ).scalar_one_or_none()

    return ultima_tipo is None or ultima_tipo == TIPO_PROPOSTA_REVISADA


def run_verificacao_sync(verificacao_id: str) -> dict:
    """
    Corpo da task Celery (R3): verifica a proposta final contra requisitos e
    acordos. Persiste resultado_ia e rodadas origem=VERIFICACAO_FINAL por item.
    """
    engine = _get_sync_engine()

    try:
        with Session(engine) as db:
            verificacao = db.execute(
                select(VerificacaoFinal).where(
                    VerificacaoFinal.id == uuid.UUID(verificacao_id)
                )
            ).scalar_one_or_none()
            if not verificacao:
                return {"error": "Verificacao nao encontrada"}

            key = _progress_key(str(verificacao.parecer_id))
            set_progress(key, 10, "Carregando proposta final e acordos...", "loading")

            rodada = db.execute(
                select(RodadaFornecedor).where(
                    RodadaFornecedor.id == verificacao.rodada_fornecedor_id
                )
            ).scalar_one_or_none()
            if not rodada:
                raise ValueError("Rodada da proposta final nao encontrada.")

            texto_proposta = None
            if rodada.texto_colado and rodada.texto_colado.strip():
                texto_proposta = rodada.texto_colado
            elif rodada.documento is not None and rodada.documento.texto_extraido:
                texto_proposta = rodada.documento.texto_extraido
            if not texto_proposta:
                raise ValueError("Proposta final sem texto extraido.")

            itens = db.execute(
                select(ItemParecer)
                .where(
                    ItemParecer.parecer_id == verificacao.parecer_id,
                    ItemParecer.estado != DESATIVADO,
                )
                .order_by(ItemParecer.numero)
            ).scalars().all()

            # R3: último acordo de cada item (última rodada com conteúdo)
            itens_payload = []
            for item in itens:
                ultima = db.execute(
                    select(RodadaAvaliacao)
                    .where(RodadaAvaliacao.item_id == item.id)
                    .order_by(RodadaAvaliacao.numero_rodada.desc())
                    .limit(1)
                ).scalar_one_or_none()
                acordo = None
                if ultima:
                    acordo = ultima.conteudo or ultima.justificativa_ia
                itens_payload.append({
                    "numero": item.numero,
                    "descricao_requisito": item.descricao_requisito,
                    "valor_requerido": item.valor_requerido,
                    "ultimo_acordo": acordo,
                })

            set_progress(key, 40, "LLM verificando proposta final contra acordos...", "llm_verifying")
            user_content = VERIFICACAO_USER_TEMPLATE.format(
                texto_proposta=texto_proposta,
                itens_json=json.dumps(itens_payload, ensure_ascii=False, indent=2),
            )
            raw = call_llm(VERIFICACAO_SYSTEM_PROMPT, user_content)
            data = extract_json(raw)

            set_progress(key, 80, "Registrando resultado da verificacao...", "saving")
            numeros_validos = {i.numero: i for i in itens}
            resultado_itens = []
            now = datetime.utcnow()

            for entry in data.get("itens", []):
                numero = entry.get("numero")
                if numero not in numeros_validos:
                    continue
                conformidade = str(entry.get("conformidade", "")).upper()
                if conformidade not in _VALID_CONFORMIDADES:
                    conformidade = "PARCIAL"
                evidencia = str(entry.get("evidencia", "")).strip()
                observacao = str(entry.get("observacao", "")).strip()
                resultado_itens.append({
                    "numero": numero,
                    "conformidade": conformidade,
                    "evidencia": evidencia,
                    "observacao": observacao,
                })

                item = numeros_validos[numero]
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
                        origem="VERIFICACAO_FINAL",
                        conteudo=evidencia,
                        veredito_ia=_CONFORMIDADE_PARA_VEREDITO[conformidade],
                        justificativa_ia=observacao,
                        criado_em=now,
                    )
                )

            verificacao.resultado_ia = {
                "itens": resultado_itens,
                "resumo": str(data.get("resumo", "")).strip(),
            }
            verificacao.status = "AGUARDANDO_VALIDACAO"
            rodada.status = "AVALIADA"
            db.commit()

            nao_conformes = sum(
                1 for i in resultado_itens if i["conformidade"] == "NAO_CONFORME"
            )
            set_progress(
                key, 100,
                f"Verificacao concluida: {len(resultado_itens)} item(ns), "
                f"{nao_conformes} nao conforme(s). Valide o resultado (W5).",
                "completed",
            )
            return {"status": "AGUARDANDO_VALIDACAO", "itens": len(resultado_itens)}
    except Exception as e:
        logger.exception("Verificacao final falhou: %s", verificacao_id)
        msg = str(e)[:500]
        try:
            with Session(_get_sync_engine()) as db:
                verificacao = db.execute(
                    select(VerificacaoFinal).where(
                        VerificacaoFinal.id == uuid.UUID(verificacao_id)
                    )
                ).scalar_one_or_none()
                if verificacao:
                    verificacao.status = "ERRO"
                    db.commit()
                    set_progress(
                        _progress_key(str(verificacao.parecer_id)),
                        100, f"Erro na verificacao: {msg}", "error",
                    )
        except Exception:
            logger.exception("Falha ao persistir erro da verificacao %s", verificacao_id)
        return {"error": msg}


def start_verificacao_in_background(verificacao_id: str) -> str:
    """Enfileira a verificação final (R3) no Celery e devolve o task id."""
    from app.worker import verificar_proposta_final_task

    task = verificar_proposta_final_task.delay(verificacao_id)
    return task.id
