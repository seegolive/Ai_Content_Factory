"""Celery application configuration."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_content_factory",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.pipeline",
        "app.workers.tasks.transcribe",
        "app.workers.tasks.analyze",
        "app.workers.tasks.process_video",
        "app.workers.tasks.distribute",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=604800,  # 7 days
    task_max_retries=3,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.pipeline.*": {"queue": "pipeline"},
        "app.workers.tasks.distribute.*": {"queue": "distribute"},
    },
)
