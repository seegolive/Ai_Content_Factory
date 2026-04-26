"""QC orchestration — delegates to VideoProcessorService."""
from app.services.video_processor import QCResult, VideoProcessorService

_processor = VideoProcessorService()


async def run_qc(clip_path: str) -> QCResult:
    return await _processor.run_qc_check(clip_path)
