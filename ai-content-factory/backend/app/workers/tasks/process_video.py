"""Video processing subtask stub."""

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_video.process_clips")
def process_clips(video_id: str):
    """Standalone clip processing task (pipeline handles inline)."""
    pass
