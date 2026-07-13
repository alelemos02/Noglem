import hashlib
import json
import logging
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
from app.models.requisito import Requisito
from app.models.rodada_avaliacao import RodadaAvaliacao
from app.services.analyzer import (
    DEFAULT_ANALYSIS_PROFILE,
    analyze_documents,
    flag_items_for_verification,
    get_profile_label,
    llm_self_review,
    normalize_analysis_profile,
    optimize_item_fields,
    recover_missing_supplier_values,
    reconciliar_escopo_fechado,
    validate_reference_grounding,
    validate_value_consistency,
    verify_flagged_items,
)
from app.services.doc_selection import eng_docs_correntes
from app.services.state_machine import evento_para_classificacao, transicionar

logger = logging.getLogger(__name__)

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


# Bump this version whenever SYSTEM_PROMPT or profile instructions change
# to automatically invalidate cached results from previous prompt versions.
# v8: escopo fechado nos requisitos aprovados (R1 nao re-extrai da engenharia).
# v9: escopo fechado forca chamada unica (sem chunk) + otimizacao preserva
#     requisito_numero (vinculo item<->requisito) + dedupe de docs de engenharia.
# v10: delimitacao anti-injecao (marcadores <<<...>>> em torno do texto dos
#      documentos + guardrail no system prompt). Muda o prompt de analise.
PROMPT_VERSION = "11"


def _compute_docs_hash(
    requisitos_payload: list[dict],
    eng_text: str,
    forn_text: str,
    disciplina: str,
    idioma_relatorio: str,
    anexos_text: str = "",
) -> str:
    # O escopo da analise e definido pelos requisitos aprovados (W1); o perfil
    # governa apenas a extracao e por isso fica fora do hash.
    requisitos_json = json.dumps(requisitos_payload, sort_keys=True, ensure_ascii=False)
    # MODEL entra na chave: trocar o modelo de analise (ex.: flash->pro) precisa
    # invalidar o cache, senao re-analisar devolve o resultado do modelo anterior.
    content = (
        f"V:{PROMPT_VERSION}\nMODEL:{settings.GEMINI_ANALYSIS_MODEL}\n"
        f"DISC:{disciplina}\nLANG:{idioma_relatorio}\n"
        f"REQ:{requisitos_json}\nENG:{eng_text}\nFORN:{forn_text}\nANEXOS:{anexos_text}"
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def run_analysis_sync(
    parecer_id: str,
    analysis_profile: str = DEFAULT_ANALYSIS_PROFILE,
):
    """
    Run analysis in-process (no Celery), suitable for background threading.

    Operacao R1: o escopo da analise vem dos requisitos aprovados pelo
    engenheiro (tabela `requisitos`, gravada na operacao W1) — nunca de uma
    lista passada por parametro.
    """
    analysis_profile = normalize_analysis_profile(analysis_profile)
    profile_label = get_profile_label(analysis_profile)
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

            # Só a versão mais recente de cada doc de engenharia — revisões de
            # spec criam duplicatas que inflavam a análise (ver doc_selection).
            eng_docs = eng_docs_correntes(list(docs))
            forn_docs = [d for d in docs if d.tipo == "fornecedor"]
            anexo_docs = [d for d in docs if d.tipo == "anexo_engenharia"]

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
            texto_anexos = "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in anexo_docs
            )

            # R1: carrega os requisitos aprovados (W1) — fonte unica do escopo
            # (aprovado_em IS NULL = rascunho ainda em revisao, nunca entra)
            requisitos = db.execute(
                select(Requisito)
                .where(
                    Requisito.parecer_id == parecer.id,
                    Requisito.ativo.is_(True),
                    Requisito.aprovado_em.isnot(None),
                )
                .order_by(Requisito.numero)
            ).scalars().all()

            if not requisitos:
                raise ValueError(
                    "Nenhum requisito aprovado encontrado. Extraia e aprove a "
                    "lista de requisitos antes de iniciar a analise."
                )

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
            requisito_por_numero = {r.numero: r for r in requisitos}

            set_progress(parecer_id, 25, "Verificando cache de analise...", "cache_lookup")
            idioma_relatorio = getattr(parecer, "idioma_relatorio", "pt")
            disciplina = getattr(parecer, "disciplina", "instrumentacao")
            docs_hash = _compute_docs_hash(
                requisitos_payload,
                texto_engenharia,
                texto_fornecedor,
                disciplina,
                idioma_relatorio,
                texto_anexos,
            )
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
                    f"Iniciando analise com LLM ({profile_label})...",
                    "llm_analysis",
                )
                result = analyze_documents(
                    texto_engenharia=texto_engenharia,
                    texto_fornecedor=texto_fornecedor,
                    texto_anexos=texto_anexos,
                    projeto=parecer.projeto,
                    fornecedor=parecer.fornecedor,
                    numero_parecer=parecer.numero_parecer,
                    on_progress=on_progress,
                    analysis_profile=analysis_profile,
                    disciplina=disciplina,
                    idioma_relatorio=idioma_relatorio,
                    itens_aprovados=requisitos_payload,
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

                # NB: avisos internos de QA (self-review/grounding/consistencia/
                # verificacao/reconciliacao) NAO vao para comentario_geral — ele e
                # exportado ao cliente. Ficam so no log (a cobertura fica no painel
                # de rastreabilidade e nos proprios itens D).

            # Supplier value recovery: refill blanks for items whose status implies
            # the supplier offered something (anti-drop / anti-blank guard).
            set_progress(
                parecer_id,
                86,
                "Recuperando valores do fornecedor ausentes...",
                "supplier_recovery",
            )
            result, recovery = recover_missing_supplier_values(
                data=result, texto_fornecedor=texto_fornecedor
            )
            logger.info(
                "Supplier recovery: checked=%d flagged=%d recovered=%d",
                recovery["items_checked"],
                recovery["items_flagged"],
                recovery["items_recovered"],
            )

            # Cross-item verification: a deterministic detector flags suspect items
            # (e.g. the same supplier value reused across distinct requirements),
            # then a stronger model (Pro) re-checks ONLY those items.
            set_progress(
                parecer_id,
                87,
                "Verificando itens com possivel erro de leitura...",
                "verification",
            )
            result, verif_flag = flag_items_for_verification(result)
            verif_review = {"reviewed": 0, "corrections": 0}
            if (
                getattr(settings, "ENABLE_LLM_VERIFIER", True)
                and verif_flag["items_flagged"] > 0
            ):
                set_progress(
                    parecer_id,
                    87,
                    f"Revisando {verif_flag['items_flagged']} item(ns) sinalizado(s) "
                    "com verificacao IA Pro...",
                    "verification",
                )
                result, verif_review = verify_flagged_items(
                    data=result,
                    texto_engenharia=texto_engenharia,
                    texto_fornecedor=texto_fornecedor,
                    flag_summary=verif_flag,
                )
            logger.info(
                "Verification: flagged=%d reviewed=%d corrections=%d",
                verif_flag["items_flagged"],
                verif_review["reviewed"],
                verif_review.get("corrections", 0),
            )

            # Field optimization: compact verbose fields via LLM before saving
            set_progress(
                parecer_id,
                88,
                "Otimizando campos da analise...",
                "optimizing_fields",
            )
            result = optimize_item_fields(result, idioma_relatorio=idioma_relatorio)

            # Reconciliação de escopo fechado: garante 1 item por requisito
            # aprovado (injeta placeholder D para faltantes) — a análise nunca
            # sai cobrindo menos do que o engenheiro aprovou.
            set_progress(
                parecer_id, 89, "Reconciliando escopo com os requisitos aprovados...",
                "reconciling",
            )
            result, reconciliacao = reconciliar_escopo_fechado(result, requisitos_payload)
            logger.info(
                "Reconciliacao escopo: aprovados=%d faltantes=%d duplicados=%s",
                reconciliacao["requisitos_aprovados"],
                reconciliacao["itens_faltantes"],
                reconciliacao["requisitos_duplicados"],
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
                status_item = item_data.get("status", "D")
                requisito_numero = item_data.get("requisito_numero")
                requisito_vinculado = (
                    requisito_por_numero.get(requisito_numero)
                    if isinstance(requisito_numero, int)
                    else None
                )
                # Estado inicial do ciclo de vida: A resolve; B/C/D/E aguardam fornecedor
                estado_inicial = transicionar(
                    "ABERTO", evento_para_classificacao(status_item)
                )

                item = ItemParecer(
                    parecer_id=parecer.id,
                    requisito_id=requisito_vinculado.id if requisito_vinculado else None,
                    numero=item_data.get("numero", 0),
                    categoria=item_data.get("categoria"),
                    descricao_requisito=item_data.get("descricao_requisito", ""),
                    referencia_engenharia=item_data.get("referencia_engenharia"),
                    referencia_fornecedor=item_data.get("referencia_fornecedor"),
                    valor_requerido=item_data.get("valor_requerido"),
                    valor_fornecedor=item_data.get("valor_fornecedor"),
                    status=status_item,
                    justificativa_tecnica=item_data.get("justificativa_tecnica", ""),
                    acao_requerida=item_data.get("acao_requerida"),
                    prioridade=item_data.get("prioridade"),
                    norma_referencia=item_data.get("norma_referencia"),
                    estado=estado_inicial,
                    verificacao_flag=item_data.get("_verificacao_flag"),
                    verificacao_nota=item_data.get("_verificacao_nota"),
                    flag_consistencia=item_data.get("_flag_consistencia"),
                    nota_revisao=item_data.get("_nota_revisao"),
                )
                # W2 (parcial): rodada 1 e a base do historico por item — R2 le daqui
                item.rodadas.append(
                    RodadaAvaliacao(
                        numero_rodada=1,
                        origem="PROPOSTA_INICIAL",
                        conteudo=item_data.get("valor_fornecedor"),
                        classificacao_ia=status_item if status_item in "ABCDE" else None,
                        justificativa_ia=item_data.get("justificativa_tecnica", ""),
                        acao_requerida=item_data.get("acao_requerida"),
                    )
                )
                db.add(item)

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
            # comentario_geral e SO o comentario gerado pela analise — os avisos de
            # QA (grounding/consistencia/verificacao/reconciliacao) ficam no log,
            # NAO no documento entregue ao cliente (evita "18 itens com possivel
            # alucinacao" no parecer). A cobertura de escopo aparece no painel de
            # rastreabilidade e nos itens D injetados.
            parecer.comentario_geral = resumo.get("comentario_geral")
            parecer.conclusao = pt.get("conclusao")
            parecer.status_processamento = "concluido"

            logger.info(
                "QA pos-cache: grounding_flag=%d consistency_flag=%d verif_flag=%d "
                "recon_faltantes=%d recon_duplicados=%s",
                grounding["items_flagged"],
                consistency["items_flagged"],
                verif_flag["items_flagged"],
                reconciliacao["itens_faltantes"],
                reconciliacao["requisitos_duplicados"],
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

    task = processar_parecer_task.delay(parecer_id, analysis_profile)

    return task.id
