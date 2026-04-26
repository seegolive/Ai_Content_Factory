"""FFmpeg-based video processing service: cut, resize, subtitle, QC."""
import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class QCIssue:
    type: str
    description: str
    severity: str = "warning"  # warning | error


@dataclass
class QCResult:
    passed: bool
    issues: List[QCIssue]
    metrics: dict


class VideoProcessingError(Exception):
    pass


class VideoProcessorService:

    async def cut_clip(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
    ) -> str:
        """Cut clip segment from video using FFmpeg with CUDA acceleration."""
        cmd = [
            "ffmpeg", "-y",
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", input_path,
            "-c:v", "h264_nvenc",
            "-c:a", "aac",
            "-crf", "23",
            "-preset", "fast",
            output_path,
        ]
        # Fallback to CPU if CUDA fails
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if "cuda" in str(e).lower() or "nvenc" in str(e).lower():
                logger.warning("CUDA encoding failed, falling back to CPU")
                cmd_cpu = [
                    "ffmpeg", "-y",
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-i", input_path,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-crf", "23",
                    "-preset", "fast",
                    output_path,
                ]
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def resize_for_platform(
        self, input_path: str, output_dir: str, platforms: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Generate platform-specific versions (16:9, 9:16, 1:1)."""
        if platforms is None:
            platforms = ["youtube", "shorts"]

        platform_specs = {
            "youtube": ("1920:1080", "output_horizontal.mp4"),
            "shorts": ("1080:1920", "output_vertical.mp4"),
            "feed": ("1080:1080", "output_square.mp4"),
        }

        results = {}
        for platform in platforms:
            if platform not in platform_specs:
                continue
            size, filename = platform_specs[platform]
            out_path = os.path.join(output_dir, filename)
            w, h = size.split(":")

            # Smart crop with blur background for aspect ratio mismatches
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", vf,
                "-c:v", "libx264", "-c:a", "aac",
                "-crf", "23", "-preset", "fast",
                out_path,
            ]
            await self._run_ffmpeg(cmd)
            results[platform] = out_path

        return results

    async def burn_subtitles(
        self,
        input_path: str,
        transcript_segments: list,
        output_path: str,
        style: Optional[dict] = None,
    ) -> str:
        """Burn subtitles onto video."""
        # Write SRT file
        srt_path = output_path.replace(".mp4", ".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(transcript_segments, 1):
                start = _seconds_to_srt(seg["start"])
                end = _seconds_to_srt(seg["end"])
                f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")

        # Subtitle style
        font_size = style.get("font_size", 48) if style else 48
        force_style = (
            f"FontSize={font_size},FontName=Arial,Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "Outline=2,Alignment=2"
        )

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"subtitles={srt_path}:force_style='{force_style}'",
            "-c:v", "libx264", "-c:a", "copy",
            output_path,
        ]
        await self._run_ffmpeg(cmd)

        try:
            os.remove(srt_path)
        except OSError:
            pass

        return output_path

    async def run_qc_check(self, clip_path: str) -> QCResult:
        """Run automated QC checks on a clip."""
        issues: List[QCIssue] = []
        metrics = {}

        # Silence detection
        silence_cmd = [
            "ffmpeg", "-i", clip_path,
            "-af", "silencedetect=noise=-30dB:d=3",
            "-f", "null", "-",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *silence_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            stderr_text = stderr.decode()
            silence_count = stderr_text.count("silence_start")
            metrics["silence_segments"] = silence_count
            if silence_count > 0:
                issues.append(QCIssue(type="silence", description=f"Found {silence_count} silence segment(s) > 3s"))
        except Exception as e:
            logger.warning(f"Silence detection failed: {e}")

        # Audio peak level check
        loudnorm_cmd = [
            "ffmpeg", "-i", clip_path,
            "-af", "loudnorm=print_format=json",
            "-f", "null", "-",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *loudnorm_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            # Parse peak from output
            stderr_text = stderr.decode()
            if '"input_tp"' in stderr_text:
                import re
                tp_match = re.search(r'"input_tp"\s*:\s*"([-\d.]+)"', stderr_text)
                if tp_match:
                    peak_db = float(tp_match.group(1))
                    metrics["peak_db"] = peak_db
                    if peak_db > -1.0:
                        issues.append(QCIssue(type="clipping", description=f"Audio peak too high: {peak_db:.1f}dB", severity="error"))
        except Exception as e:
            logger.warning(f"Loudnorm check failed: {e}")

        passed = not any(i.severity == "error" for i in issues)
        return QCResult(passed=passed, issues=issues, metrics=metrics)

    async def _run_ffmpeg(self, cmd: List[str]) -> bytes:
        """Run FFmpeg subprocess with timeout and error handling."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)  # 30 min
        except asyncio.TimeoutError:
            proc.kill()
            raise VideoProcessingError("FFmpeg timed out after 30 minutes")

        if proc.returncode != 0:
            raise VideoProcessingError(
                f"FFmpeg failed (code {proc.returncode}): {stderr.decode()[-1000:]}"
            )
        return stdout


def _seconds_to_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
