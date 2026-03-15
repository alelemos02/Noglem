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
    task_time_limit=600,  # 10 min max per task
    task_soft_time_limit=540,  # soft limit at 9 min
)

celery_app.autodiscover_tasks(["app.services"])
