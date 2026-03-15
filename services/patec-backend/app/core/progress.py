"""Simple progress tracking via Redis for background analysis tasks."""

import json
import logging

import redis

from app.core.config import settings

_redis_client = None
logger = logging.getLogger(__name__)


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def set_progress(parecer_id: str, percent: int, message: str, stage: str = ""):
    """Store analysis progress for a parecer."""
    data = json.dumps({"percent": percent, "message": message, "stage": stage})
    try:
        _get_redis().setex(f"analysis_progress:{parecer_id}", 3600, data)
    except Exception:
        logger.exception("Failed to write progress to Redis for parecer_id=%s", parecer_id)


def get_progress(parecer_id: str) -> dict | None:
    """Retrieve analysis progress for a parecer."""
    try:
        data = _get_redis().get(f"analysis_progress:{parecer_id}")
        if data:
            return json.loads(data)
    except Exception:
        logger.exception("Failed to read progress from Redis for parecer_id=%s", parecer_id)
    return None


def clear_progress(parecer_id: str):
    """Clear progress data after analysis completes."""
    try:
        _get_redis().delete(f"analysis_progress:{parecer_id}")
    except Exception:
        logger.exception("Failed to clear progress in Redis for parecer_id=%s", parecer_id)
