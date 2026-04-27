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


def _test_nvenc_encoder(codec: str) -> bool:
    """Return True if the given NVENC codec actually works (driver + hardware check)."""
    try:
        test = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=black:s=1280x720:r=25:d=0.1",
                "-c:v", codec, "-frames:v", "2",
                "-f", "null", "-"
            ],
            capture_output=True, text=True, timeout=15
        )
        return test.returncode == 0
    except Exception:
        return False


def _detect_best_encoder() -> str:
    """Detect best available encoder: av1_nvenc > h264_nvenc > libx264."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders", "-hide_banner"],
            capture_output=True, text=True, timeout=10
        )
        encoders = result.stdout
        # Prefer AV1 NVENC (RTX 40xx) — smaller files, better quality
        if "av1_nvenc" in encoders and _test_nvenc_encoder("av1_nvenc"):
            return "av1_nvenc"
        # Fall back to H.264 NVENC
        if "h264_nvenc" in encoders and _test_nvenc_encoder("h264_nvenc"):
            return "h264_nvenc"
        return "libx264"
    except Exception:
        return "libx264"


# Cache encoder detection — checked once at startup
_BEST_ENCODER: Optional[str] = None


def get_encoder() -> str:
    global _BEST_ENCODER
    if _BEST_ENCODER is None:
        _BEST_ENCODER = _detect_best_encoder()
        logger.info(f"[VideoProcessor] Encoder selected: {_BEST_ENCODER}")
    return _BEST_ENCODER


def get_encode_params(source_height: int) -> dict:
    """Return adaptive encoding params based on source resolution."""
    if source_height >= 1440:  # 2K source (Seego GG: 2560x1440)
        return {"cq": "18", "crf": "18", "preset": "medium", "bitrate": "8M"}
    elif source_height >= 1080:
        return {"cq": "21", "crf": "20", "preset": "fast", "bitrate": "5M"}
    else:
        return {"cq": "23", "crf": "22", "preset": "fast", "bitrate": "3M"}


def build_video_encode_flags(encoder: str, params: dict) -> list:
    """Return FFmpeg video encode flags for the given encoder."""
    if encoder == "av1_nvenc":
        return ["-c:v", "av1_nvenc", "-rc:v", "vbr", "-cq:v", params["cq"],
                "-b:v", params["bitrate"], "-maxrate:v", str(int(params["bitrate"][:-1]) * 2) + "M"]
    elif encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-rc:v", "vbr", "-cq:v", params["cq"],
                "-b:v", params["bitrate"], "-maxrate:v", str(int(params["bitrate"][:-1]) * 2) + "M"]
    else:
        return ["-c:v", "libx264", "-crf", params["crf"], "-preset", params["preset"]]


def build_cpu_encode_flags(params: dict) -> list:
    """Return CPU fallback FFmpeg video encode flags."""
    return ["-c:v", "libx264", "-crf", params["crf"], "-preset", params["preset"]]


async def _get_video_height(video_path: str) -> int:
    """Probe video height using ffprobe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-select_streams", "v:0",
            "-show_entries", "stream=height", "-of", "csv=p=0", video_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return int(stdout.decode().strip()) if stdout.strip() else 1080
    except Exception:
        return 1080


class VideoProcessorService:

    async def cut_clip(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
    ) -> str:
        """Cut clip segment from video using FFmpeg with CUDA/NVENC acceleration."""
        source_height = await _get_video_height(input_path)
        params = get_encode_params(source_height)
        encoder = get_encoder()

        hw_accel = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] if encoder in ("av1_nvenc", "h264_nvenc") else []
        cmd = (
            ["ffmpeg", "-y"]
            + hw_accel
            + ["-ss", str(start_time), "-to", str(end_time), "-i", input_path]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )

        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc") and ("cuda" in str(e).lower() or "nvenc" in str(e).lower()):
                logger.warning(f"NVENC encoding failed, falling back to libx264: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y", "-ss", str(start_time), "-to", str(end_time), "-i", input_path]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
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

        source_height = await _get_video_height(input_path)
        params = get_encode_params(source_height)
        encoder = get_encoder()

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

            cmd = (
                ["ffmpeg", "-y", "-i", input_path, "-vf", vf]
                + build_video_encode_flags(encoder, params)
                + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
            )
            try:
                await self._run_ffmpeg(cmd)
            except VideoProcessingError as e:
                if encoder in ("av1_nvenc", "h264_nvenc") and ("cuda" in str(e).lower() or "nvenc" in str(e).lower()):
                    logger.warning(f"NVENC failed for {platform}, falling back to libx264")
                    cmd_cpu = (
                        ["ffmpeg", "-y", "-i", input_path, "-vf", vf]
                        + build_cpu_encode_flags(params)
                        + ["-c:a", "aac", "-movflags", "+faststart", out_path]
                    )
                    await self._run_ffmpeg(cmd_cpu)
                else:
                    raise
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

    async def resize_to_vertical_smart(
        self,
        input_path: str,
        output_path: str,
        game_profile=None,
        channel_config=None,
    ) -> str:
        """
        Convert 16:9 source (typically 2560x1440) → 1080x1920 9:16 vertical.
        Uses game-specific crop mode from GameCropProfile.
        Falls back to blur_pillarbox if no profile provided.
        """
        source_h = channel_config.obs_canvas_height if channel_config else 1440
        source_w = channel_config.obs_canvas_width if channel_config else 2560
        mode = (game_profile.vertical_crop_mode if game_profile else None) or "blur_pillarbox"

        if mode == "smart_offset":
            return await self._crop_smart_offset(input_path, output_path, game_profile, source_w, source_h)
        elif mode == "dual_zone":
            return await self._crop_dual_zone(input_path, output_path, game_profile, source_w, source_h)
        else:
            return await self._crop_blur_pillarbox(input_path, output_path, source_w, source_h)

    async def _crop_blur_pillarbox(
        self, input_path: str, output_path: str, source_w: int, source_h: int
    ) -> str:
        """
        Default safe mode: 16:9 video centred with blurred pillarbox sides → 1080x1920.
        No content is cropped; safest for unknown games.
        """
        encoder = get_encoder()
        params = {"cq": "19", "crf": "20", "preset": "fast", "bitrate": "5M"}
        vf = (
            "split[original][copy];"
            "[copy]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=luma_radius=30:luma_power=3[blurred];"
            "[original]scale=1080:-2[scaled];"
            "[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
        )
        cmd = (
            ["ffmpeg", "-y", "-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC pillarbox failed, falling back: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y", "-i", input_path, "-vf", vf]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def _crop_smart_offset(
        self, input_path: str, output_path: str, profile, source_w: int, source_h: int
    ) -> str:
        """
        Crop an 810px-wide strip from the 2560px source (default from left)
        then scale to 1080x1920. Facecam in the top-left corner is preserved.
        """
        crop_h = source_h          # 1440
        crop_w = int(source_h * 9 / 16)  # 810

        anchor = (profile.crop_anchor if profile else None) or "left"
        x_offset = (profile.crop_x_offset if profile else None) or 0

        if anchor == "left":
            x = max(0, x_offset)
        elif anchor == "right":
            x = max(0, source_w - crop_w - x_offset)
        else:
            x = max(0, (source_w - crop_w) // 2)
        x = min(x, source_w - crop_w)

        encoder = get_encoder()
        params = {"cq": "18", "crf": "18", "preset": "medium", "bitrate": "8M"}
        vf = f"crop={crop_w}:{crop_h}:{x}:0,scale=1080:1920"
        cmd = (
            ["ffmpeg", "-y", "-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        await self._run_ffmpeg(cmd)
        return output_path

    async def _crop_dual_zone(
        self, input_path: str, output_path: str, profile, source_w: int, source_h: int
    ) -> str:
        """
        Split 1080x1920 into:
          - Top zone (38%=730px): full-width facecam
          - Bottom zone (62%=1190px): gameplay center crop
        Valorant layout: facecam top, gameplay center-focused.
        """
        out_w, out_h = 1080, 1920
        split = (profile.dual_zone_split_ratio if profile else None) or 0.38

        fc_zone_h = int(out_h * split)
        gp_zone_h = out_h - fc_zone_h

        fc_x = (profile.facecam_x if profile else None) or 0
        fc_y = (profile.facecam_y if profile else None) or 0
        fc_w = (profile.facecam_width if profile else None) or source_w
        fc_h = (profile.facecam_height if profile else None) or int(source_h * split)

        gp_center_x = (profile.gameplay_crop_center_x if profile else None) or (source_w // 2)
        gp_crop_h = source_h - fc_h
        gp_crop_w = max(1, int(gp_crop_h * out_w / gp_zone_h))
        gp_x = max(0, gp_center_x - gp_crop_w // 2)
        gp_x = min(gp_x, source_w - gp_crop_w)
        gp_y = fc_h

        encoder = get_encoder()
        params = {"cq": "18", "crf": "18", "preset": "medium", "bitrate": "8M"}
        filter_complex = (
            f"[0:v]crop={fc_w}:{fc_h}:{fc_x}:{fc_y},scale={out_w}:{fc_zone_h}[fc];"
            f"[0:v]crop={gp_crop_w}:{gp_crop_h}:{gp_x}:{gp_y},scale={out_w}:{gp_zone_h}[gp];"
            f"[fc][gp]vstack=inputs=2[output]"
        )
        cmd = (
            ["ffmpeg", "-y", "-i", input_path,
             "-filter_complex", filter_complex,
             "-map", "[output]", "-map", "0:a"]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        await self._run_ffmpeg(cmd)
        return output_path

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
