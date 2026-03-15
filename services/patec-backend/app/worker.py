import logging

from celery import Celery

from app.core.config import settings
from app.api.v1.endpoints.analise import ANALYSIS_PROFILE_LABELS

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
    # We delay the import to avoid circular dependencies and ensure 
    # the application context is loaded only in the worker process
    from app.services.tasks import run_analysis_sync
    
    result = run_analysis_sync(
        parecer_id=parecer_id, 
        analysis_profile=analysis_profile
    )
    
    return result
