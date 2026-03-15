import hashlib
import logging
import threading
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - ensure all model mappers are registered
from app.core.config import settings
from app.core.progress import set_progress
from app.models.cache_analise import CacheAnalise
from app.models.documento import Documento
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.services.analyzer import (
    DEFAULT_ANALYSIS_PROFILE,
    analyze_documents,
    llm_self_review,
    normalize_analysis_profile,
    validate_reference_grounding,
    validate_value_consistency,
)

logger = logging.getLogger(__name__)

_sync_engine = None
ANALYSIS_PROFILE_LABELS = {
    "triagem_tecnica": "Triagem Tecnica",
    "conformidade_tecnica": "Conformidade Tecnica",
    "auditoria_tecnica_completa": "Auditoria Tecnica Completa",
}


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


# Bump this version whenever SYSTEM_PROMPT or profile instructions change
# to automatically invalidate cached results from previous prompt versions.
PROMPT_VERSION = "3"


def _compute_docs_hash(eng_text: str, forn_text: str, analysis_profile: str) -> str:
    content = f"V:{PROMPT_VERSION}\nPROFILE:{analysis_profile}\nENG:{eng_text}\nFORN:{forn_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def run_analysis_sync(
    parecer_id: str,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
):
    """Run analysis in-process (no Celery), suitable for background threading."""
    analysis_profile = normalize_analysis_profile(analysis_profile)
    profile_label = ANALYSIS_PROFILE_LABELS.get(
        analysis_profile, ANALYSIS_PROFILE_LABELS[DEFAULT_ANALYSIS_PROFILE]
    )
    engine = _get_sync_engine()
    set_progress(parecer_id, 5, f"Iniciando processamento ({profile_label})...", "starting")

    try:
        with Session(engine) as db:
            parecer = db.execute(
                select(Parecer).where(Parecer.id == uuid.UUID(parecer_id))
            ).scalar_one_or_none()

            if not parecer:
                logger.error("Parecer %s not found", parecer_id)
                set_progress(parecer_id, 100, "Parecer nao encontrado", "error")
                return {"error": "Parecer nao encontrado"}

            parecer.status_processamento = "processando"
            db.commit()

            set_progress(parecer_id, 15, "Carregando documentos...", "loading_documents")
            docs = db.execute(
                select(Documento).where(Documento.parecer_id == parecer.id)
            ).scalars().all()

            eng_docs = [d for d in docs if d.tipo == "engenharia"]
            forn_docs = [d for d in docs if d.tipo == "fornecedor"]

            if not eng_docs:
                raise ValueError("Nenhum documento de engenharia encontrado")
            if not forn_docs:
                raise ValueError("Nenhum documento do fornecedor encontrado")

            texto_engenharia = "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in eng_docs
            )
            texto_fornecedor = "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in forn_docs
            )

            set_progress(parecer_id, 25, "Verificando cache de analise...", "cache_lookup")
            docs_hash = _compute_docs_hash(texto_engenharia, texto_fornecedor, analysis_profile)
            cached = db.execute(
                select(CacheAnalise).where(CacheAnalise.hash_documentos == docs_hash)
            ).scalar_one_or_none()

            _llm_step = {"n": 0}

            def on_progress(msg: str):
                # Increment progress from 35 to 70 during LLM analysis
                _llm_step["n"] += 1
                pct = min(70, 35 + _llm_step["n"] * 5)
                set_progress(parecer_id, pct, msg, "llm_analysis")
                logger.info("Progress %s (%d%%): %s", parecer_id, pct, msg)

            if cached:
                set_progress(
                    parecer_id,
                    70,
                    f"Resultado encontrado em cache ({profile_label}), reutilizando...",
                    "cache_hit",
                )
                logger.info("Cache hit for hash %s", docs_hash[:16])
                result = cached.resultado
            else:
                set_progress(
                    parecer_id,
                    35,
                    f"Iniciando analise com IA ({profile_label})...",
                    "llm_analysis",
                )
                result = analyze_documents(
                    texto_engenharia=texto_engenharia,
                    texto_fornecedor=texto_fornecedor,
                    projeto=parecer.projeto,
                    fornecedor=parecer.fornecedor,
                    numero_parecer=parecer.numero_parecer,
                    on_progress=on_progress,
                    analysis_profile=analysis_profile,
                )
                db.add(
                    CacheAnalise(
                        hash_documentos=docs_hash,
                        resultado=result,
                    )
                )
                logger.info("Cached result for hash %s", docs_hash[:16])

            set_progress(
                parecer_id,
                75,
                "Validando referencias para reduzir alucinacoes...",
                "reference_validation",
            )
            result, grounding = validate_reference_grounding(
                data=result,
                texto_engenharia=texto_engenharia,
                texto_fornecedor=texto_fornecedor,
            )
            logger.info(
                "Reference grounding: checked=%d flagged=%d eng_miss=%d forn_miss=%d",
                grounding["items_checked"],
                grounding["items_flagged"],
                grounding["eng_reference_misses"],
                grounding["forn_reference_misses"],
            )

            # Value consistency validation (anti-false-negative)
            set_progress(
                parecer_id,
                80,
                "Validando consistencia de classificacoes...",
                "consistency_validation",
            )
            result, consistency = validate_value_consistency(
                data=result,
                texto_fornecedor=texto_fornecedor,
            )
            logger.info(
                "Value consistency: checked=%d flagged=%d",
                consistency["items_checked"],
                consistency["items_flagged"],
            )

            # Optional LLM self-review for flagged items
            if (
                getattr(settings, "ENABLE_LLM_SELF_REVIEW", False)
                and consistency["items_flagged"] > 0
            ):
                set_progress(
                    parecer_id,
                    85,
                    "Revisando classificacoes sinalizadas com segunda verificacao IA...",
                    "self_review",
                )
                result, review_summary = llm_self_review(
                    data=result,
                    texto_fornecedor=texto_fornecedor,
                    consistency_summary=consistency,
                )
                logger.info(
                    "Self-review: reviewed=%d corrections=%d",
                    review_summary["reviewed"],
                    review_summary.get("corrections", 0),
                )

                if review_summary.get("corrections", 0) > 0:
                    review_warning = (
                        f"Revisao automatica por IA: {review_summary['corrections']} "
                        "item(ns) corrigido(s) apos segunda verificacao. "
                        "Itens marcados com [CORRECAO_AUTO_REVISAO]."
                    )
                    parecer.comentario_geral = (
                        f"{parecer.comentario_geral}\n\n{review_warning}".strip()
                        if parecer.comentario_geral
                        else review_warning
                    )

            set_progress(parecer_id, 90, "Salvando resultados no banco...", "saving_results")
            db.execute(
                ItemParecer.__table__.delete().where(ItemParecer.parecer_id == parecer.id)
            )
            db.execute(
                Recomendacao.__table__.delete().where(Recomendacao.parecer_id == parecer.id)
            )

            pt = result.get("parecer_tecnico", result)
            resumo = pt.get("resumo_executivo", {})
            itens = pt.get("itens", [])

            for item_data in itens:
                db.add(
                    ItemParecer(
                        parecer_id=parecer.id,
                        numero=item_data.get("numero", 0),
                        categoria=item_data.get("categoria"),
                        descricao_requisito=item_data.get("descricao_requisito", ""),
                        referencia_engenharia=item_data.get("referencia_engenharia"),
                        referencia_fornecedor=item_data.get("referencia_fornecedor"),
                        valor_requerido=item_data.get("valor_requerido"),
                        valor_fornecedor=item_data.get("valor_fornecedor"),
                        status=item_data.get("status", "D"),
                        justificativa_tecnica=item_data.get("justificativa_tecnica", ""),
                        acao_requerida=item_data.get("acao_requerida"),
                        prioridade=item_data.get("prioridade"),
                        norma_referencia=item_data.get("norma_referencia"),
                    )
                )

            recomendacoes = pt.get("recomendacoes", [])
            for i, texto in enumerate(recomendacoes):
                db.add(
                    Recomendacao(
                        parecer_id=parecer.id,
                        texto=texto if isinstance(texto, str) else str(texto),
                        ordem=i + 1,
                    )
                )

            parecer.total_itens = resumo.get("total_itens", len(itens))
            parecer.total_aprovados = resumo.get("aprovados", 0)
            parecer.total_aprovados_comentarios = resumo.get("aprovados_com_comentarios", 0)
            parecer.total_rejeitados = resumo.get("rejeitados", 0)
            parecer.total_info_ausente = resumo.get("informacao_ausente", 0)
            parecer.total_itens_adicionais = resumo.get("itens_adicionais_fornecedor", 0)
            parecer.parecer_geral = resumo.get("parecer_geral")
            parecer.comentario_geral = resumo.get("comentario_geral")
            parecer.conclusao = pt.get("conclusao")
            parecer.status_processamento = "concluido"

            if grounding["items_flagged"] > 0:
                warning = (
                    f"Validacao de referencias: {grounding['items_flagged']} item(ns) "
                    "marcado(s) com possivel alucinacao."
                )
                parecer.comentario_geral = (
                    f"{parecer.comentario_geral}\n\n{warning}".strip()
                    if parecer.comentario_geral
                    else warning
                )

            if consistency["items_flagged"] > 0:
                consistency_warning = (
                    f"Validacao de consistencia: {consistency['items_flagged']} item(ns) "
                    "com possivel erro de leitura (termos requeridos encontrados no texto "
                    "do fornecedor). Verifique os itens marcados com [VALIDACAO_CONSISTENCIA]."
                )
                parecer.comentario_geral = (
                    f"{parecer.comentario_geral}\n\n{consistency_warning}".strip()
                    if parecer.comentario_geral
                    else consistency_warning
                )

            db.commit()
            set_progress(parecer_id, 100, "Analise concluida com sucesso.", "completed")
            logger.info("Analysis completed for parecer %s: %d items", parecer_id, len(itens))
            return {
                "status": "concluido",
                "total_itens": len(itens),
                "parecer_geral": resumo.get("parecer_geral"),
            }
    except Exception as e:
        logger.exception("Analysis failed for parecer %s", parecer_id)
        error_msg = str(e)[:500]  # Limit error message length
        # Always try to set progress first (Redis is fast and unlikely to fail)
        try:
            set_progress(parecer_id, 100, f"Erro na analise: {error_msg}", "error")
        except Exception:
            logger.exception("Failed to set error progress for parecer %s", parecer_id)

        # Then try to update the database
        for attempt in range(2):
            try:
                error_engine = _get_sync_engine()
                with Session(error_engine) as db:
                    db.execute(
                        text(
                            "UPDATE pareceres "
                            "SET status_processamento = 'erro', "
                            "    comentario_geral = :msg "
                            "WHERE id = :pid"
                        ),
                        {"msg": f"Erro na analise: {error_msg}", "pid": str(parecer_id)},
                    )
                    db.commit()
                    logger.info("Updated parecer %s status to error (attempt %d)", parecer_id, attempt + 1)
                    break
            except Exception:
                logger.exception(
                    "Failed to persist error status for parecer %s (attempt %d)",
                    parecer_id, attempt + 1,
                )
                if attempt == 0:
                    # Reset engine on first failure to get a fresh connection
                    global _sync_engine
                    _sync_engine = None

        return {"error": error_msg}


def start_analysis_in_background(
    parecer_id: str,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
) -> str:
    """Start analysis via Celery queue and return the task id."""
    from app.worker import processar_parecer_task
    
    # Trigger task asynchronously using Celery
    task = processar_parecer_task.delay(parecer_id, analysis_profile)
    
    return task.id
