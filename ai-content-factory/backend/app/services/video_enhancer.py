"""Video Enhancement Service — Real-ESRGAN 2× upscale + FFmpeg downscale to 1440p."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

# Target output: 1440p vertical (1440×2560)
_TARGET_W = 1440
_TARGET_H = 2560
_MODEL_NAME = "RealESRGAN_x2plus"


class VideoEnhancerService:
    """Enhance a clip from 1080p to 1440p using Real-ESRGAN 2× + FFmpeg downscale."""

    async def enhance(
        self,
        input_path: str,
        output_path: str,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> dict:
        """Upscale clip to 1440p. Returns metadata dict on success."""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input clip not found: {input_path}")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._enhance_sync, input_path, output_path, progress_cb
        )
        return result

    def _enhance_sync(
        self,
        input_path: str,
        output_path: str,
        progress_cb: Optional[Callable[[int], None]],
    ) -> dict:
        with tempfile.TemporaryDirectory(prefix="enhance_") as tmp:
            frames_dir = os.path.join(tmp, "frames_in")
            upscaled_dir = os.path.join(tmp, "frames_up")
            os.makedirs(frames_dir)
            os.makedirs(upscaled_dir)

            # 1. Probe source
            probe = self._probe(input_path)
            fps = probe["fps"]
            duration = probe["duration"]

            if progress_cb:
                progress_cb(5)

            # 2. Extract frames (no audio — audio muxed later)
            logger.info(f"[Enhancer] Extracting frames from {input_path}")
            self._run(["ffmpeg", "-y", "-i", input_path,
                       "-vf", f"fps={fps}",
                       "-q:v", "1",
                       os.path.join(frames_dir, "frame_%06d.png")])

            frame_count = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
            logger.info(f"[Enhancer] {frame_count} frames extracted")

            if progress_cb:
                progress_cb(15)

            # 3. Real-ESRGAN upscale (CUDA)
            logger.info(f"[Enhancer] Running Real-ESRGAN {_MODEL_NAME}")
            self._run_realesrgan(frames_dir, upscaled_dir, progress_cb)

            if progress_cb:
                progress_cb(85)

            # 4. Mux upscaled frames + original audio → 2160p temp file
            tmp_2160 = os.path.join(tmp, "upscaled_2160p.mp4")
            self._run(["ffmpeg", "-y",
                       "-framerate", str(fps),
                       "-i", os.path.join(upscaled_dir, "frame_%06d.png"),
                       "-i", input_path,
                       "-map", "0:v", "-map", "1:a?",
                       "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                       "-c:a", "copy",
                       tmp_2160])

            if progress_cb:
                progress_cb(92)

            # 5. Downscale 2160p → 1440p (Lanczos)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self._run(["ffmpeg", "-y", "-i", tmp_2160,
                       "-vf", f"scale={_TARGET_W}:{_TARGET_H}:flags=lanczos",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                       "-c:a", "copy",
                       output_path])

            if progress_cb:
                progress_cb(100)

            out_size = os.path.getsize(output_path)
            logger.info(f"[Enhancer] Done → {output_path} ({out_size//1024//1024}MB)")

            return {
                "width": _TARGET_W,
                "height": _TARGET_H,
                "fps": fps,
                "duration": duration,
                "file_size_mb": round(out_size / 1024 / 1024, 1),
            }

    def _run_realesrgan(
        self,
        input_dir: str,
        output_dir: str,
        progress_cb: Optional[Callable[[int], None]],
    ) -> None:
        """Run Real-ESRGAN via realesrgan-ncnn-vulkan or basicsr Python API."""
        # Try Python API first (basicsr/realesrgan installed via pip)
        try:
            self._run_realesrgan_python(input_dir, output_dir, progress_cb)
            return
        except (ImportError, Exception) as e:
            logger.warning(f"[Enhancer] Python Real-ESRGAN failed ({e}), trying CLI fallback")

        # CLI fallback: realesrgan-ncnn-vulkan binary
        binary = self._find_realesrgan_binary()
        if binary:
            self._run([binary, "-i", input_dir, "-o", output_dir,
                       "-n", _MODEL_NAME, "-s", "2", "-f", "png"])
        else:
            raise RuntimeError(
                "Real-ESRGAN not available. Install with: pip install realesrgan basicsr"
            )

    def _run_realesrgan_python(
        self,
        input_dir: str,
        output_dir: str,
        progress_cb: Optional[Callable[[int], None]],
    ) -> None:
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                        num_block=23, num_grow_ch=32, scale=2)
        upsampler = RealESRGANer(
            scale=2,
            model_path=f"https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/{_MODEL_NAME}.pth",
            model=model,
            tile=256,   # tile to fit 12GB VRAM
            tile_pad=10,
            pre_pad=0,
            half=True,  # fp16 for RTX 4070
            gpu_id=0 if torch.cuda.is_available() else None,
        )

        frames = sorted(f for f in os.listdir(input_dir) if f.endswith(".png"))
        total = len(frames)
        for i, fname in enumerate(frames):
            import cv2
            import numpy as np
            img = cv2.imread(os.path.join(input_dir, fname), cv2.IMREAD_UNCHANGED)
            output, _ = upsampler.enhance(img, outscale=2)
            cv2.imwrite(os.path.join(output_dir, fname), output)
            if progress_cb and i % max(1, total // 20) == 0:
                pct = 15 + int((i / total) * 70)
                progress_cb(pct)

    def _find_realesrgan_binary(self) -> Optional[str]:
        import shutil
        return shutil.which("realesrgan-ncnn-vulkan")

    def _probe(self, path: str) -> dict:
        import json
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(r.stdout)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        num, den = video.get("r_frame_rate", "30/1").split("/")
        fps = round(int(num) / max(1, int(den)), 3)
        return {
            "fps": fps,
            "width": video.get("width"),
            "height": video.get("height"),
            "duration": float(video.get("duration", 0)),
        }

    def _run(self, cmd: list) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd[:3])}\n{result.stderr[-500:]}")
