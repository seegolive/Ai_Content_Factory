"""AI Analysis subtask stub."""

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.analyze.analyze_video")
def analyze_video(video_id: str):
    """Standalone AI analysis task (pipeline handles inline)."""
    pass
