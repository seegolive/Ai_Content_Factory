"""FFmpeg-based video processing service: cut, resize, subtitle, QC."""

import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger

# Montserrat Bold bundled in assets — available via ./backend:/app volume mount
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Montserrat-Bold.ttf")
_FONT_PATH = os.path.normpath(_FONT_PATH)


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
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=black:s=1280x720:r=25:d=0.1",
                "-c:v",
                codec,
                "-frames:v",
                "2",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return test.returncode == 0
    except Exception:
        return False


def _detect_best_encoder() -> str:
    """Detect best available encoder: h264_nvenc > libx264.

    AV1 (av1_nvenc) is intentionally skipped: clips must be playable in all
    browsers via the <video> element, and AV1 hardware decode support is not
    guaranteed across browsers / OS combinations.  H.264 has universal support.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        encoders = result.stdout
        # H.264 NVENC — GPU-accelerated, universally browser-compatible
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
        return [
            "-c:v",
            "av1_nvenc",
            "-rc:v",
            "vbr",
            "-cq:v",
            params["cq"],
            "-b:v",
            params["bitrate"],
            "-maxrate:v",
            str(int(params["bitrate"][:-1]) * 2) + "M",
        ]
    elif encoder == "h264_nvenc":
        return [
            "-c:v",
            "h264_nvenc",
            "-rc:v",
            "vbr",
            "-cq:v",
            params["cq"],
            "-b:v",
            params["bitrate"],
            "-maxrate:v",
            str(int(params["bitrate"][:-1]) * 2) + "M",
        ]
    else:
        return ["-c:v", "libx264", "-crf", params["crf"], "-preset", params["preset"]]


def build_cpu_encode_flags(params: dict) -> list:
    """Return CPU fallback FFmpeg video encode flags."""
    return ["-c:v", "libx264", "-crf", params["crf"], "-preset", params["preset"]]


def _seek_args(start_time: Optional[float], end_time: Optional[float]) -> list:
    """Build FFmpeg input-seek args for a combined cut+process single pass.

    Both args go BEFORE -i so FFmpeg uses fast input seeking.
    -ss {start}  → seek to start position
    -to {end}    → stop reading at this absolute source timestamp
    """
    args: list = []
    if start_time is not None and start_time > 0:
        args += ["-ss", f"{start_time:.3f}"]
    if end_time is not None:
        args += ["-to", f"{end_time:.3f}"]
    return args


async def _get_video_height(video_path: str) -> int:
    """Probe video height using ffprobe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "csv=p=0",
            video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return int(stdout.decode().strip()) if stdout.strip() else 1080
    except Exception:
        return 1080


class VideoProcessorService:
    async def hook_first_cut(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        peak_time: float,
        hook_duration: float = 4.0,
    ) -> str:
        """Non-linear hook-first edit: show peak preview → rewind → build → payoff.

        Structure:
          [HOOK: peak → peak+hook_duration]  ← climax preview (stops scroll)
          [BUILD: start → peak]              ← tension build-up
          [PAYOFF: peak → end]               ← climax + reaction
        """
        buildup_sec = peak_time - start_time
        if buildup_sec < 8:
            # Not enough build-up — fall back to linear cut
            logger.info(f"[VideoProcessor] Hook-first skipped: build-up only {buildup_sec:.1f}s")
            return await self.cut_clip(input_path, output_path, start_time, end_time)

        hook_end = min(peak_time + hook_duration, end_time)
        encoder = get_encoder()
        source_height = await _get_video_height(input_path)
        params = get_encode_params(source_height)

        filter_complex = (
            f"[0:v]trim=start={peak_time}:end={hook_end},setpts=PTS-STARTPTS[vhook];"
            f"[0:v]trim=start={start_time}:end={peak_time},setpts=PTS-STARTPTS[vbuild];"
            f"[0:v]trim=start={peak_time}:end={end_time},setpts=PTS-STARTPTS[vpayoff];"
            f"[vhook][vbuild][vpayoff]concat=n=3:v=1:a=0[vout];"
            f"[0:a]atrim=start={peak_time}:end={hook_end},asetpts=PTS-STARTPTS[ahook];"
            f"[0:a]atrim=start={start_time}:end={peak_time},asetpts=PTS-STARTPTS[abuild];"
            f"[0:a]atrim=start={peak_time}:end={end_time},asetpts=PTS-STARTPTS[apayoff];"
            f"[ahook][abuild][apayoff]concat=n=3:v=0:a=1[aout]"
        )

        v_flags = build_video_encode_flags(encoder, params)
        cmd = (
            ["ffmpeg", "-y", "-i", input_path,
             "-filter_complex", filter_complex,
             "-map", "[vout]", "-map", "[aout]"]
            + v_flags
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
            logger.info(
                f"[VideoProcessor] Hook-first edit done: "
                f"hook={hook_duration:.1f}s build={buildup_sec:.1f}s"
            )
            return output_path
        except VideoProcessingError as e:
            logger.warning(f"Hook-first NVENC failed, falling back to libx264: {e}")
            cmd_cpu = (
                ["ffmpeg", "-y", "-i", input_path,
                 "-filter_complex", filter_complex,
                 "-map", "[vout]", "-map", "[aout]"]
                + build_cpu_encode_flags(params)
                + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
            )
            await self._run_ffmpeg(cmd_cpu)
            return output_path

    async def cut_clip(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
    ) -> str:
        """Cut clip segment from video.

        Strategy (fastest first):
          1. Stream copy — no re-encode, nearly instant (<1s per clip)
          2. NVENC re-encode fallback — if stream copy produces corrupt output
          3. CPU (libx264) — last resort
        """
        # Stream copy: fastest possible cut, no GPU/CPU encode needed
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-to",
            str(end_time),
            "-i",
            input_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]
        try:
            await self._run_ffmpeg(cmd_copy)
            return output_path
        except VideoProcessingError as e:
            logger.warning(f"Stream copy cut failed, falling back to re-encode: {e}")

        # Re-encode fallback (needed if source has no keyframes near cut point)
        source_height = await _get_video_height(input_path)
        params = get_encode_params(source_height)
        encoder = get_encoder()

        cmd = (
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-to",
                str(end_time),
                "-i",
                input_path,
            ]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC cut failed, falling back to libx264: {e}")
                cmd_cpu = (
                    [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        str(start_time),
                        "-to",
                        str(end_time),
                        "-i",
                        input_path,
                    ]
                    + build_cpu_encode_flags(params)
                    + [
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-movflags",
                        "+faststart",
                        output_path,
                    ]
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
                if encoder in ("av1_nvenc", "h264_nvenc") and (
                    "cuda" in str(e).lower() or "nvenc" in str(e).lower()
                ):
                    logger.warning(
                        f"NVENC failed for {platform}, falling back to libx264"
                    )
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
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vf",
            f"subtitles={srt_path}:force_style='{force_style}'",
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
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
            "ffmpeg",
            "-i",
            clip_path,
            "-af",
            "silencedetect=noise=-30dB:d=3",
            "-f",
            "null",
            "-",
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
                issues.append(
                    QCIssue(
                        type="silence",
                        description=f"Found {silence_count} silence segment(s) > 3s",
                    )
                )
        except Exception as e:
            logger.warning(f"Silence detection failed: {e}")

        # Audio peak level check
        loudnorm_cmd = [
            "ffmpeg",
            "-i",
            clip_path,
            "-af",
            "loudnorm=print_format=json",
            "-f",
            "null",
            "-",
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
                    if peak_db > 0.0:
                        issues.append(
                            QCIssue(
                                type="clipping",
                                description=f"Audio peak too high: {peak_db:.1f}dB",
                                severity="error",
                            )
                        )
                    elif peak_db > -1.0:
                        issues.append(
                            QCIssue(
                                type="clipping",
                                description=f"Audio peak near clipping: {peak_db:.1f}dB",
                                severity="warning",
                            )
                        )
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
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """
        Convert 16:9 source (typically 2560x1440) → 1080x1920 9:16 vertical.
        Uses game-specific crop mode from GameCropProfile.
        Falls back to blur_pillarbox if no profile provided.

        When start_time/end_time are provided, the cut and crop are combined
        into a single FFmpeg pass (no intermediate horizontal file).
        """
        source_h = channel_config.obs_canvas_height if channel_config else 1440
        source_w = channel_config.obs_canvas_width if channel_config else 2560
        # Resolve crop mode: channel_config default is user's explicit choice and takes priority.
        # Game profile can override only if channel_config has no explicit preference.
        mode = (
            (channel_config.default_vertical_crop_mode if channel_config else None)
            or (game_profile.vertical_crop_mode if game_profile else None)
            or "blur_pillarbox"
        )

        # Auto-detect: if source is already portrait, skip conversion entirely.
        if source_h > source_w and mode != "passthrough":
            logger.info(
                f"[VideoProcessor] source is already vertical ({source_w}x{source_h}), forcing passthrough"
            )
            mode = "passthrough"

        logger.info(
            f"[VideoProcessor] resize_to_vertical mode={mode} src={source_w}x{source_h}"
            + (f" [{start_time:.1f}s–{end_time:.1f}s]" if start_time is not None else "")
        )
        if mode == "passthrough":
            return await self._crop_passthrough(
                input_path, output_path, start_time, end_time
            )
        elif mode == "smart_offset":
            return await self._crop_smart_offset(
                input_path, output_path, game_profile, source_w, source_h, start_time, end_time
            )
        elif mode == "dual_zone":
            return await self._crop_dual_zone(
                input_path, output_path, game_profile, source_w, source_h, start_time, end_time
            )
        elif mode == "center_crop":
            return await self._crop_center(
                input_path, output_path, source_w, source_h, start_time, end_time
            )
        elif mode == "blur_letterbox":
            return await self._crop_blur_letterbox(
                input_path, output_path, source_w, source_h, start_time, end_time
            )
        else:
            return await self._crop_blur_pillarbox(
                input_path, output_path, source_w, source_h, start_time, end_time
            )

    async def _crop_passthrough(
        self,
        input_path: str,
        output_path: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """Re-encode already-vertical source to 1080x1920, no crop/blur."""
        encoder = get_encoder()
        params = {"cq": "18", "crf": "18", "preset": "medium", "bitrate": "8M"}
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC passthrough failed, falling back to CPU: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def _crop_center(
        self,
        input_path: str,
        output_path: str,
        source_w: int,
        source_h: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """
        Simple center crop: take the 9:16 portion from the middle of the 16:9 frame.
        Gameplay fills the full 1080x1920 canvas — no bars, no blur.
        Best for games where the important action is in the center.
        """
        crop_h = source_h
        crop_w = int(source_h * 9 / 16)
        x = (source_w - crop_w) // 2
        x = max(0, min(x, source_w - crop_w))

        encoder = get_encoder()
        params = {"cq": "18", "crf": "18", "preset": "medium", "bitrate": "8M"}
        vf = f"crop={crop_w}:{crop_h}:{x}:0,scale=1080:1920"
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC center crop failed, falling back: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def _crop_blur_letterbox(
        self,
        input_path: str,
        output_path: str,
        source_w: int,
        source_h: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """
        Shorts-style blur letterbox (9:16 canvas = 1080x1920):

          Layout:
            [ BLUR TOP    ]  ~353px  — blur fills top gap
            [ 16:9 VIDEO  ]  ~1214px — 200% zoom, centered (left/right overflow cropped ~540px each side)
            [ BLUR BOTTOM ]  ~353px  — blur fills bottom gap

          Content pipeline:
            1. Scale video to 200% of canvas width (2×1080 = 2160px wide)
            2. Center-overlay on 1080x1920 canvas → left/right auto-cropped by canvas bounds
            3. Blur fills only top/bottom gaps — no explicit crop step needed
        """
        encoder = get_encoder()
        params = {"cq": "19", "crf": "20", "preset": "fast", "bitrate": "5M"}

        vf = (
            # Split into background (bg) and foreground (fg)
            "split=2[bg][fg];"
            # Background: fill full 1080x1920, heavy blur, darken 18%
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "boxblur=luma_radius=50:luma_power=4:chroma_radius=50:chroma_power=4,"
            "colorchannelmixer=rr=0.82:gg=0.82:bb=0.82[blurred];"
            # Foreground: scale to 200% of canvas width (2160px) → center on canvas
            # Left/right overflow (~540px each side) is auto-cropped by canvas bounds
            # -2 ensures even height for NVENC compatibility
            "[fg]scale=2160:-2[big];"
            # Composite: centered — blur only fills top/bottom gaps
            "[blurred][big]overlay=(W-w)/2:(H-h)/2"
        )
        # Use NVENC for encoding (GPU). Decode stays on CPU because software filters
        # (split, boxblur, overlay) require CPU frames — hwaccel cuda would break them.
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC blur_letterbox failed, falling back to CPU: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def _crop_blur_pillarbox(
        self,
        input_path: str,
        output_path: str,
        source_w: int,
        source_h: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
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
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        try:
            await self._run_ffmpeg(cmd)
        except VideoProcessingError as e:
            if encoder in ("av1_nvenc", "h264_nvenc"):
                logger.warning(f"NVENC pillarbox failed, falling back: {e}")
                cmd_cpu = (
                    ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
                    + build_cpu_encode_flags(params)
                    + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
                )
                await self._run_ffmpeg(cmd_cpu)
            else:
                raise
        return output_path

    async def _crop_smart_offset(
        self,
        input_path: str,
        output_path: str,
        profile,
        source_w: int,
        source_h: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """
        Crop an 810px-wide strip from the 2560px source (default from left)
        then scale to 1080x1920. Facecam in the top-left corner is preserved.
        """
        crop_h = source_h  # 1440
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
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"] + seek + ["-i", input_path, "-vf", vf]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        await self._run_ffmpeg(cmd)
        return output_path

    async def _crop_dual_zone(
        self,
        input_path: str,
        output_path: str,
        profile,
        source_w: int,
        source_h: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
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

        gp_center_x = (profile.gameplay_crop_center_x if profile else None) or (
            source_w // 2
        )
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
        seek = _seek_args(start_time, end_time)
        cmd = (
            ["ffmpeg", "-y"]
            + seek
            + ["-i", input_path, "-filter_complex", filter_complex, "-map", "[output]", "-map", "0:a"]
            + build_video_encode_flags(encoder, params)
            + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path]
        )
        await self._run_ffmpeg(cmd)
        return output_path

    async def burn_captions(
        self,
        input_path: str,
        output_path: str,
        segments: list,
        clip_start: float = 0.0,
        clip_end: float = float("inf"),
        hook_duration: float = 0.0,
        peak_time: Optional[float] = None,
    ) -> str:
        """Burn Montserrat Bold captions from transcript segments into the video.

        Handles timestamp remapping for hook-first edited clips:
          output[0 → hook_dur]           = source[peak_time → peak_time+hook_dur]
          output[hook_dur → hook_dur+build] = source[clip_start → peak_time]
          output[hook_dur+build → end]    = source[peak_time → clip_end]
        """
        if not os.path.exists(_FONT_PATH):
            logger.warning(f"[Caption] Font not found at {_FONT_PATH}, skipping captions")
            return input_path

        # Build ASS subtitle file — avoids argument-list-too-long from chained drawtext
        ass_header = (
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
            "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, "
            "Encoding\n"
            "Style: Default,Montserrat,52,&H00FFFFFF,&H000000FF,&H00000000,&H88000000,"
            "1,0,0,0,100,100,0,0,3,3,0,2,20,20,350,1\n"
            # Rewind marker: smaller, centered, shown briefly at hook→build transition
            "Style: Rewind,Montserrat,40,&H00FFFFFF,&H000000FF,&H00000000,&HCC000000,"
            "1,0,0,0,100,100,0,0,3,2,0,5,40,40,960,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        ass_events = []

        # Add "X DETIK SEBELUMNYA" rewind marker at hook→build transition
        if peak_time is not None and hook_duration > 0:
            rewind_sec = int(peak_time - clip_start)
            rewind_text = f"{rewind_sec} DETIK SEBELUMNYA..."
            # Show for 1.5s starting at hook_duration
            ass_events.append(
                f"Dialogue: 1,{_fmt_ass(hook_duration)},{_fmt_ass(hook_duration + 1.5)},"
                f"Rewind,,0,0,0,,{rewind_text}"
            )

        for seg in segments:
            src_start = seg.get("start", 0.0)
            src_end = seg.get("end", src_start + 1.0)
            text = seg.get("text", "").strip()
            if not text:
                continue
            # Skip segments outside clip range
            if src_end < clip_start or src_start > clip_end:
                continue
            out_start = _remap_timestamp(src_start, clip_start, peak_time, hook_duration, clip_end)
            out_end = _remap_timestamp(src_end, clip_start, peak_time, hook_duration, clip_end)
            if out_start is None or out_end is None or out_start >= out_end or out_start < 0:
                continue
            wrapped = _wrap_caption(text).replace("\n", "\\N")
            ass_events.append(
                f"Dialogue: 0,{_fmt_ass(out_start)},{_fmt_ass(out_end)},"
                f"Default,,0,0,0,,{wrapped}"
            )

        if not ass_events:
            logger.info("[Caption] No subtitle entries for this clip, skipping")
            return input_path

        ass_content = ass_header + "\n".join(ass_events)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ass", delete=False, encoding="utf-8"
        ) as f:
            f.write(ass_content)
            ass_path = f.name

        fonts_dir = os.path.dirname(_FONT_PATH)
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"subtitles={ass_path}:fontsdir={fonts_dir}",
            "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-c:a", "copy", "-movflags", "+faststart",
            output_path,
        ]
        try:
            await self._run_ffmpeg(cmd)
            logger.info(f"[Caption] Burned {len(ass_events)} subtitle entries")
            return output_path
        finally:
            try:
                os.remove(ass_path)
            except OSError:
                pass

    async def _run_ffmpeg(self, cmd: List[str]) -> bytes:
        """Run FFmpeg subprocess with timeout and error handling."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=1800
            )  # 30 min
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


def _fmt_srt(t: float) -> str:
    return _seconds_to_srt(max(0.0, t))


def _fmt_ass(t: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc"""
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int((t % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _remap_timestamp(
    src_t: float,
    clip_start: float,
    peak_time: Optional[float],
    hook_dur: float,
    clip_end: float = float("inf"),
) -> Optional[float]:
    """Map source video timestamp to hook-first output timestamp.

    For linear clips (no peak_time): output = src_t - clip_start
    For hook-first clips:
      source[peak → peak+hook_dur] → output[0 → hook_dur]
      source[clip_start → peak]    → output[hook_dur → hook_dur+build]
      source[peak → clip_end]      → output[hook_dur+build → end]
    """
    if src_t < clip_start or src_t > clip_end:
        return None
    if peak_time is None or hook_dur == 0:
        return src_t - clip_start

    build_dur = peak_time - clip_start
    # Hook segment: peak_time → peak_time + hook_dur
    if peak_time <= src_t <= min(peak_time + hook_dur, clip_end):
        return src_t - peak_time
    # Build segment: clip_start → peak_time
    if clip_start <= src_t < peak_time:
        return hook_dur + (src_t - clip_start)
    # Payoff segment: peak_time → clip_end
    if src_t > peak_time:
        return hook_dur + build_dur + (src_t - peak_time)
    return None


def _wrap_caption(text: str, max_chars: int = 28) -> str:
    """Wrap caption text at word boundary, max 2 lines."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= 2:
            break
    if current and len(lines) < 2:
        lines.append(current)
    return "\n".join(lines)
