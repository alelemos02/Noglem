import logging

from celery import Celery

from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "patec_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configure prefork limits if needed
    worker_concurrency=2,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max analysis time
)

logger = logging.getLogger(__name__)

# Register tasks
@celery_app.task(bind=True, name="processar_parecer")
def processar_parecer_task(self, parecer_id: str, analysis_profile: str):
    """
    Celery task wrapper around the existing run_analysis_sync function.
    """
    logger.info("Starting analysis for parecer %s with profile %s", parecer_id, analysis_profile)
    from app.services.tasks import run_analysis_sync

    result = run_analysis_sync(
        parecer_id=parecer_id,
        analysis_profile=analysis_profile,
    )

    return result


@celery_app.task(bind=True, name="processar_vinculacao")
def processar_vinculacao_task(self, rodada_id: str):
    """Bloco 23 do fluxo: LLM sugere vínculos resposta→item (provisórios até W3)."""
    logger.info("Starting vinculacao for rodada %s", rodada_id)
    from app.services.ciclo import run_vinculacao_sync

    return run_vinculacao_sync(rodada_id)


@celery_app.task(bind=True, name="avaliar_rodada")
def avaliar_rodada_task(self, rodada_id: str):
    """Bloco 24 do fluxo (R2): avalia respostas confirmadas contra pendências e histórico."""
    logger.info("Starting avaliacao for rodada %s", rodada_id)
    from app.services.ciclo import run_avaliacao_sync

    return run_avaliacao_sync(rodada_id)


@celery_app.task(bind=True, name="verificar_proposta_final")
def verificar_proposta_final_task(self, verificacao_id: str):
    """Bloco 32 do fluxo (R3): verifica a proposta final contra os acordos do caso."""
    logger.info("Starting verificacao final %s", verificacao_id)
    from app.services.verificador_final import run_verificacao_sync

    return run_verificacao_sync(verificacao_id)


@celery_app.task(bind=True, name="comparar_spec")
def comparar_spec_task(self, versao_id: str):
    """Bloco 36 do fluxo (R4): compara a nova revisão da spec contra os requisitos do BD."""
    logger.info("Starting spec diff %s", versao_id)
    from app.services.spec_diff import run_spec_diff_sync

    return run_spec_diff_sync(versao_id)


@celery_app.task(bind=True, name="indexar_documento")
def indexar_documento_task(self, documento_id: str):
    """Indexação RAG (chunk + embed + store) em background — não bloqueia o upload."""
    logger.info("Starting RAG indexing for documento %s", documento_id)
    from app.services.indexer import index_document_sync

    return index_document_sync(documento_id)


@celery_app.task(bind=True, name="ocr_documento")
def ocr_documento_task(self, documento_id: str, conteudo_b64: str):
    """OCR/transcricao multimodal de imagem/PDF escaneado em background (A2).

    Recebe os bytes do arquivo em base64 — o worker nao compartilha o
    filesystem da API, entao o conteudo viaja pela fila.
    """
    import base64

    logger.info("Starting OCR for documento %s", documento_id)
    from app.services.ocr import run_ocr_sync

    return run_ocr_sync(documento_id, base64.b64decode(conteudo_b64))
