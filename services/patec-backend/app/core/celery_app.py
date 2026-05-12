from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "patec",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task (matches worker.py)
    task_soft_time_limit=3540,  # soft limit at 59 min
)

celery_app.autodiscover_tasks(["app.services"])
