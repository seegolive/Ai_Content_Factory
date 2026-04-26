"""Transcription subtask — used when transcription is dispatched as a standalone task."""
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.transcribe.transcribe_video")
def transcribe_video(video_id: str):
    """Standalone transcription task (called from pipeline internally)."""
    pass  # Pipeline handles transcription inline via _stage_transcription
