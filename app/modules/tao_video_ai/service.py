from __future__ import annotations

import inspect
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

import numpy as np
from PIL import Image

ProgressCB = Callable[[int, str, str], None]


def _parse_duration(value: object) -> float:
    """Safely parse duration that may be a float, 'MM:SS', 'HH:MM:SS', or N/A.
    Never raises; always returns a float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s.upper() in ("N/A", "NA", "NULL", "NONE"):
        return 0.0
    if ":" not in s:
        try:
            return float(s)
        except ValueError:
            return 0.0
    parts = s.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return 0.0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    try:
        return float(s)
    except ValueError:
        return 0.0


class VideoGenerationCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoProfile:
    mode: str
    width: int
    height: int
    duration: float
    fps: float
    num_frames: int
    steps: int
    guidance: float


# ---------------------------------------------------------------------------
# Model-type detection
# ---------------------------------------------------------------------------

def _model_type(model_id: str) -> str:
    """Detect model family from the HuggingFace model ID string.

    Returns one of: 'wan', 'ltx', 'cogvideo', 'svd', 'unknown'.
    """
    name = (model_id or "").lower()
    if "wan" in name:
        return "wan"
    if "ltx" in name:
        return "ltx"
    if "cogvideo" in name:
        return "cogvideo"
    if "stable-video" in name or "svd" in name:
        return "svd"
    return "unknown"


# ---------------------------------------------------------------------------
# Frame-count rounding per model family
# ---------------------------------------------------------------------------

def _round_cogvideox_frames(duration: float, fps: float) -> int:
    # CogVideoX expects 8n+1 frames. Keep the nearest supported value >= 17.
    target = max(17, int(round(duration * fps)))
    n = max(2, int(round((target - 1) / 8)))
    return 8 * n + 1


def _round_wan_frames(duration: float, fps: float) -> int:
    # Wan expects 4k+1 frames (e.g. 33, 49, 65, 81). Nearest supported >= 17.
    target = max(17, int(round(duration * fps)))
    k = max(4, int(round((target - 1) / 4)))
    return 4 * k + 1


def _round_ltx_frames(duration: float, fps: float) -> int:
    # LTX-Video works in 8-frame buckets (8, 16, 24, 32...). >= 8.
    target = max(8, int(round(duration * fps)))
    n = max(1, int(round(target / 8)))
    return max(8, n * 8)


def _round_svd_frames(duration: float, fps: float) -> int:
    # SVD commonly emits 25 frames.
    return 25


_FRAME_ROUNDERS = {
    "wan": _round_wan_frames,
    "ltx": _round_ltx_frames,
    "cogvideo": _round_cogvideox_frames,
    "svd": _round_svd_frames,
    "unknown": _round_cogvideox_frames,
}


# ---------------------------------------------------------------------------
# Video profiles per model family
# ---------------------------------------------------------------------------

def _video_profile(mode: str, quality: str, duration: float, fps: int,
                   model_type: str = "cogvideo") -> VideoProfile:
    duration = min(6.0, max(2.0, _parse_duration(duration)))
    fps = min(30, max(8, int(fps)))
    q = (quality or "balanced").lower()
    rounder = _FRAME_ROUNDERS.get(model_type, _round_cogvideox_frames)

    if model_type == "wan":
        # Wan 2.2 native: 1280x704 (landscape) for 5B, 832x480 for 1.3B
        if q == "draft":
            w, h, steps, guidance = 832, 480, 25, 5.0
        elif q == "high":
            w, h, steps, guidance = 1280, 704, 50, 5.0
        else:
            w, h, steps, guidance = 1024, 576, 35, 5.0
        num_frames = rounder(duration, fps)
        return VideoProfile(mode, w, h, duration, fps, num_frames, steps, guidance)

    if model_type == "ltx":
        # LTX-Video: fast, ~15-20s/clip on RTX 5060 Ti
        if q == "draft":
            w, h, steps, guidance = 512, 320, 20, 3.0
        elif q == "high":
            w, h, steps, guidance = 768, 512, 30, 3.0
        else:
            w, h, steps, guidance = 704, 448, 25, 3.0
        num_frames = rounder(duration, fps)
        return VideoProfile(mode, w, h, duration, fps, num_frames, steps, guidance)

    # CogVideoX default profiles (original behaviour)
    if mode == "text_to_video":
        if q == "draft":
            w, h, steps = 576, 320, 28
        elif q == "high":
            w, h, steps = 720, 480, 50
        else:
            w, h, steps = 720, 480, 36
        return VideoProfile(mode, w, h, duration, fps, rounder(duration, fps), steps, 6.0)
    # SVD works most reliably around 1024x576 and commonly emits 25 frames.
    if q == "draft":
        w, h, steps = 768, 432, 20
    elif q == "high":
        w, h, steps = 1024, 576, 30
    else:
        w, h, steps = 1024, 576, 25
    return VideoProfile(mode, w, h, duration, fps, 25, steps, 3.0)


class VideoAIWorkspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def new_output(self) -> Path:
        return self.root / f"video_ai_{uuid4().hex}.mp4"

    def media_path(self, name: str) -> Path:
        safe = Path(name).name
        path = self.root / safe
        if not path.exists() or path.suffix.lower() != ".mp4":
            raise FileNotFoundError(safe)
        return path


class LocalVideoAIService:
    """Local-only video generation service.

    Defaults target a 16 GB NVIDIA GPU (RTX 5060 Ti):
      * T2V: Wan-AI/Wan2.2-TI2V-5B-Diffusers  (720p, Apache 2.0)
      * I2V: Wan-AI/Wan2.2-TI2V-5B-Diffusers  (text+image → video)
      * Fallback T2V: CogVideoX-2b, Wan2.1-T2V-1.3B
      * Fallback I2V: SVD img2vid-xt-1-1, LTX-Video

    Set AIVF_T2V_MODEL / AIVF_I2V_MODEL env vars to change the model.
    Set AIVF_VIDEO_LOCAL_ONLY=1 to use cached models only (no download).
    """

    def __init__(self, model_root: str | Path, workspace: VideoAIWorkspace):
        self.model_root = Path(model_root).resolve()
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace
        # Wan 2.2 TI2V-5B — best quality for RTX 5060 Ti 16GB
        self.t2v_model = os.getenv("AIVF_T2V_MODEL", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
        self.i2v_model = os.getenv("AIVF_I2V_MODEL", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
        self.local_only = os.getenv("AIVF_VIDEO_LOCAL_ONLY", "0").strip() == "1"
        self._pipeline = None
        self._pipeline_key = None
        self._lock = threading.RLock()

    def status(self) -> dict:
        try:
            import torch
            cuda = bool(torch.cuda.is_available())
            gpu = torch.cuda.get_device_name(0) if cuda else None
            cap = list(torch.cuda.get_device_capability(0)) if cuda else None
            total = int(torch.cuda.get_device_properties(0).total_memory) if cuda else 0
            torch_version = torch.__version__
            cuda_version = torch.version.cuda
        except Exception as exc:
            return {"ready": False, "error": str(exc), "t2v_model": self.t2v_model, "i2v_model": self.i2v_model}
        return {
            "ready": cuda,
            "cuda": cuda,
            "gpu": gpu,
            "capability": cap,
            "vram_bytes": total,
            "torch": torch_version,
            "cuda_runtime": cuda_version,
            "t2v_model": self.t2v_model,
            "t2v_type": _model_type(self.t2v_model),
            "i2v_model": self.i2v_model,
            "i2v_type": _model_type(self.i2v_model),
            "local_only": self.local_only,
            "active_pipeline": self._pipeline_key,
            "ffmpeg": shutil.which("ffmpeg"),
        }

    def _ensure_cuda(self):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA không khả dụng. AI video local yêu cầu GPU NVIDIA/CUDA.")
        # Real kernel smoke test, not only is_available().
        x = torch.ones((16, 16), device="cuda", dtype=torch.float16)
        _ = x @ x
        torch.cuda.synchronize()
        return torch

    def _unload(self):
        if self._pipeline is not None:
            try:
                self._pipeline.to("cpu")
            except Exception:
                pass
        self._pipeline = None
        self._pipeline_key = None
        try:
            import gc, torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Pipeline loading — detects model family and uses correct diffusers class
    # ------------------------------------------------------------------

    def _load_t2v(self):
        """Load the text-to-video pipeline for the configured model."""
        torch = self._ensure_cuda()
        key = ("t2v", self.t2v_model)
        if self._pipeline_key == key and self._pipeline is not None:
            return self._pipeline
        self._unload()
        mtype = _model_type(self.t2v_model)

        if mtype == "wan":
            pipe = self._load_wan_t2v(torch)
        elif mtype == "ltx":
            pipe = self._load_ltx_t2v(torch)
        else:
            pipe = self._load_cogvideo_t2v(torch)

        self._pipeline, self._pipeline_key = pipe, key
        return pipe

    def _load_i2v(self):
        """Load the image-to-video pipeline for the configured model."""
        torch = self._ensure_cuda()
        key = ("i2v", self.i2v_model)
        if self._pipeline_key == key and self._pipeline is not None:
            return self._pipeline
        self._unload()
        mtype = _model_type(self.i2v_model)

        if mtype == "wan":
            pipe = self._load_wan_i2v(torch)
        elif mtype == "ltx":
            pipe = self._load_ltx_i2v(torch)
        else:
            pipe = self._load_svd_i2v(torch)

        self._pipeline, self._pipeline_key = pipe, key
        return pipe

    def _load_wan_t2v(self, torch):
        """Load Wan T2V pipeline (WanPipeline)."""
        try:
            from diffusers import WanPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers chua co WanPipeline. Cap nhat diffusers >= 0.32."
            ) from exc
        kwargs = {"torch_dtype": torch.bfloat16, "local_files_only": self.local_only}
        pipe = WanPipeline.from_pretrained(self.t2v_model, **kwargs)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.vae.enable_tiling()
            pipe.vae.enable_slicing()
        except Exception:
            pass
        return pipe

    def _load_wan_i2v(self, torch):
        """Load Wan TI2V (text+image → video) pipeline.

        WanImageToVideoPipeline accepts both ``image`` and ``prompt``,
        making it a true TI2V model (not just silent I2V like SVD).
        """
        try:
            from diffusers import WanImageToVideoPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers chua co WanImageToVideoPipeline. Cap nhat diffusers >= 0.32."
            ) from exc
        kwargs = {"torch_dtype": torch.bfloat16, "local_files_only": self.local_only}
        pipe = WanImageToVideoPipeline.from_pretrained(self.i2v_model, **kwargs)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.vae.enable_tiling()
            pipe.vae.enable_slicing()
        except Exception:
            pass
        return pipe

    def _load_ltx_t2v(self, torch):
        """Load LTX-Video T2V pipeline (fastest video model on RTX 5060 Ti)."""
        try:
            from diffusers import LTXVideoPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers chua co LTXVideoPipeline. Cap nhat diffusers >= 0.31."
            ) from exc
        kwargs = {"torch_dtype": torch.bfloat16, "local_files_only": self.local_only}
        pipe = LTXVideoPipeline.from_pretrained(self.t2v_model, **kwargs)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.vae.enable_tiling()
        except Exception:
            pass
        return pipe

    def _load_ltx_i2v(self, torch):
        """Load LTX-Video I2V pipeline."""
        try:
            from diffusers import LTXVideoImageToVideoPipeline
        except ImportError:
            # Fallback: some diffusers versions use a different class name
            try:
                from diffusers import LTXVideoImg2VideoPipeline as LTXVideoImageToVideoPipeline
            except ImportError as exc:
                raise RuntimeError(
                    "Diffusers chua co LTXVideoImageToVideoPipeline. Cap nhat diffusers >= 0.31."
                ) from exc
        kwargs = {"torch_dtype": torch.bfloat16, "local_files_only": self.local_only}
        pipe = LTXVideoImageToVideoPipeline.from_pretrained(self.i2v_model, **kwargs)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.vae.enable_tiling()
        except Exception:
            pass
        return pipe

    def _load_cogvideo_t2v(self, torch):
        """Load CogVideoX T2V pipeline (original fallback)."""
        try:
            from diffusers import CogVideoXPipeline
        except Exception as exc:
            raise RuntimeError("Diffusers hien tai chua co CogVideoXPipeline") from exc
        kwargs = {"torch_dtype": torch.float16, "local_files_only": self.local_only}
        pipe = CogVideoXPipeline.from_pretrained(self.t2v_model, **kwargs)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.vae.enable_tiling()
            pipe.vae.enable_slicing()
        except Exception:
            pass
        return pipe

    def _load_svd_i2v(self, torch):
        """Load Stable Video Diffusion I2V pipeline (original fallback)."""
        try:
            from diffusers import StableVideoDiffusionPipeline
        except Exception as exc:
            raise RuntimeError("Diffusers hien tai chua co StableVideoDiffusionPipeline") from exc
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            self.i2v_model,
            torch_dtype=torch.float16,
            variant="fp16",
            local_files_only=self.local_only,
        )
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe.to("cuda")
        try:
            pipe.enable_vae_slicing()
        except Exception:
            pass
        return pipe

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _progress_kwargs(pipe, cancel_event: threading.Event | None, progress: ProgressCB | None, start: int, end: int):
        params = inspect.signature(pipe.__call__).parameters
        if "callback_on_step_end" not in params:
            return {}
        def cb(_pipe, step, timestep, callback_kwargs):
            if cancel_event is not None and cancel_event.is_set():
                raise VideoGenerationCancelled("Đã dừng tạo video")
            total = max(1, getattr(_pipe, "num_timesteps", 0) or 1)
            pct = start + int((end - start) * min(1.0, (step + 1) / total))
            if progress:
                progress(pct, "Đang sinh frame AI", f"Diffusion step {step + 1}")
            return callback_kwargs
        return {"callback_on_step_end": cb}

    @staticmethod
    def _normalize_frames(raw) -> list[Image.Image]:
        if raw is None:
            return []
        if hasattr(raw, "detach"):
            raw = raw.detach().float().cpu().numpy()
        if isinstance(raw, np.ndarray):
            arr = raw
            if arr.ndim == 5:
                arr = arr[0]
            if arr.ndim == 4 and arr.shape[1] in (1, 3, 4):
                arr = np.transpose(arr, (0, 2, 3, 1))
            frames = []
            for x in arr:
                x = np.asarray(x)
                if x.dtype != np.uint8:
                    if x.min() < 0:
                        x = (x + 1.0) / 2.0
                    x = np.clip(x, 0, 1) * 255.0
                    x = x.astype(np.uint8)
                frames.append(Image.fromarray(x[..., :3]).convert("RGB"))
            return frames
        if isinstance(raw, (list, tuple)):
            if len(raw) == 1 and isinstance(raw[0], (list, tuple, np.ndarray)):
                return LocalVideoAIService._normalize_frames(raw[0])
            out = []
            for f in raw:
                if isinstance(f, Image.Image):
                    out.append(f.convert("RGB"))
                else:
                    a = np.asarray(f)
                    if a.dtype != np.uint8:
                        a = np.clip(a, 0, 1) * 255
                        a = a.astype(np.uint8)
                    out.append(Image.fromarray(a[..., :3]).convert("RGB"))
            return out
        return []

    @staticmethod
    def _ffmpeg_encoder() -> str:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("Không tìm thấy ffmpeg trong PATH")
        try:
            probe = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10)
            if "h264_nvenc" in (probe.stdout or ""):
                return "h264_nvenc"
        except Exception:
            pass
        return "libx264"

    @staticmethod
    def _ffprobe(output: Path) -> dict:
        """Probe the encoded timeline; frame count/duration is authoritative."""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
                if sibling.is_file():
                    ffprobe = str(sibling)
        if not ffprobe:
            raise RuntimeError("ffprobe not found in PATH or beside ffmpeg")
        cp = subprocess.run(
            [ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=avg_frame_rate,r_frame_rate,nb_frames,nb_read_frames,duration,width,height,codec_name",
             "-show_entries", "format=duration", "-of", "json", str(output)],
            capture_output=True, text=True, timeout=120,
        )
        if cp.returncode != 0:
            raise RuntimeError("FFprobe failed: " + (cp.stderr or "")[-1200:])
        meta = json.loads(cp.stdout)
        stream = (meta.get("streams") or [{}])[0]
        duration = _parse_duration(stream.get("duration") or (meta.get("format") or {}).get("duration") or 0)
        frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
        def ratio(value):
            try:
                a, b = str(value or "0/0").split("/", 1)
                return float(a) / float(b) if float(b) else 0.0
            except (TypeError, ValueError, ZeroDivisionError):
                return 0.0
        avg_fps = ratio(stream.get("avg_frame_rate"))
        effective_fps = frames / duration if frames > 0 and duration > 0 else avg_fps
        return {"avg_fps": avg_fps, "r_fps": ratio(stream.get("r_frame_rate")),
                "effective_fps": effective_fps, "frames": frames, "duration": duration,
                "width": int(stream.get("width") or 0), "height": int(stream.get("height") or 0),
                "codec": stream.get("codec_name")}

    @staticmethod
    def _encode_mp4(frames: Iterable[Image.Image], output: Path, duration: float, progress: ProgressCB | None = None):
        """Encode model frames to a real constant-frame-rate 30fps MP4.

        Generative video backends (notably SVD) may only create ~25 unique frames for
        a 2-6 second shot. That is normal model behavior; it must not leak into the
        master timeline as an 8-10fps stream. FFmpeg owns the presentation timeline:
        source timestamps describe the requested duration, then fps=30 duplicates/
        schedules frames onto a strict CFR stream. QA probes the encoded result.
        """
        frames = list(frames)
        if not frames:
            raise RuntimeError("Model không trả về frame video")
        duration = max(0.25, _parse_duration(duration))
        output.parent.mkdir(parents=True, exist_ok=True)
        encoder = LocalVideoAIService._ffmpeg_encoder()
        source_fps = max(1.0, len(frames) / duration)
        target_fps = 30
        with tempfile.TemporaryDirectory(prefix="aivf_video_frames_") as td:
            td = Path(td)
            for i, frame in enumerate(frames):
                frame.convert("RGB").save(td / f"frame_{i:05d}.png", compress_level=1)
                if progress and i % max(1, len(frames)//8) == 0:
                    progress(90 + int(5 * (i + 1) / len(frames)), "Đóng gói frame", f"{i+1}/{len(frames)}")

            def command(codec: str):
                cmd = [
                    shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", f"{source_fps:.9f}", "-i", str(td / "frame_%05d.png"),
                    "-an", "-c:v", codec,
                ]
                if codec == "h264_nvenc":
                    cmd += ["-preset", "p5", "-cq", "20"]
                else:
                    cmd += ["-preset", "medium", "-crf", "20"]
                cmd += [
                    "-vf", f"fps={target_fps}",
                    "-r", str(target_fps), "-fps_mode", "cfr",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
                ]
                return cmd

            proc = subprocess.run(command(encoder), capture_output=True, text=True)
            if (proc.returncode != 0 or not output.exists() or output.stat().st_size <= 0) and encoder == "h264_nvenc":
                output.unlink(missing_ok=True)
                encoder = "libx264"
                proc = subprocess.run(command(encoder), capture_output=True, text=True)
            if proc.returncode != 0 or not output.exists() or output.stat().st_size <= 0:
                raise RuntimeError("FFmpeg encode lỗi: " + (proc.stderr or "")[-2000:])

        probe = LocalVideoAIService._ffprobe(output)
        if probe["effective_fps"] < 29.0 or probe["duration"] <= 0 or probe["frames"] <= 0:
            raise RuntimeError(f"VIDEO_FPS_NORMALIZE_FAILED: {probe}")
        print(f"VIDEO FPS SOURCE: {source_fps:.3f}")
        print(f"VIDEO FPS EFFECTIVE: {probe['effective_fps']:.3f}")
        print(f"VIDEO FPS TARGET: {target_fps}")
        print(f"FPS NORMALIZED: {probe['avg_fps']:.3f}")
        print(f"CODEC: {probe['codec']}")
        print(f"DURATION: {probe['duration']:.3f}")
        print(f"FRAME COUNT: {probe['frames']}")
        print("VIDEO QA: PASS")
        if progress:
            progress(98, "Đang xác minh MP4", f"{encoder} · CFR {target_fps}fps")
        return {"encoder": encoder, "fps": probe["effective_fps"], "frames": probe["frames"],
                "source_fps": source_fps, "target_fps": target_fps, "probe": probe}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_text(self, prompt: str, *, quality="balanced", duration=3.0, fps=16, seed=0,
                      cancel_event=None, progress: ProgressCB | None = None) -> dict:
        """Text-to-video generation.

        Supports Wan 2.2, LTX-Video, and CogVideoX depending on AIVF_T2V_MODEL.
        """
        if not prompt or len(prompt.strip()) < 3:
            raise ValueError("Mô tả video quá ngắn")
        mtype = _model_type(self.t2v_model)
        profile = _video_profile("text_to_video", quality, duration, fps, mtype)
        if progress: progress(5, "Nạp model video", self.t2v_model)
        with self._lock:
            pipe = self._load_t2v()
            torch = self._ensure_cuda()
            if cancel_event is not None and cancel_event.is_set():
                raise VideoGenerationCancelled("Đã dừng tạo video")
            generator = torch.Generator(device="cuda").manual_seed(int(seed) if int(seed) >= 0 else 0)

            # Build model-specific kwargs
            kwargs = dict(
                prompt=prompt.strip(), width=profile.width, height=profile.height,
                num_frames=profile.num_frames, num_inference_steps=profile.steps,
                guidance_scale=profile.guidance, generator=generator,
            )
            # Wan and CogVideoX support negative_prompt; LTX does too in recent diffusers
            if mtype in ("wan", "cogvideo"):
                kwargs["negative_prompt"] = (
                    "blurry, low quality, distorted, watermark, text, deformed, "
                    "bad anatomy, extra limbs, low resolution"
                )
            kwargs.update(self._progress_kwargs(pipe, cancel_event, progress, 10, 88))
            if progress: progress(10, "Đang sinh video AI", f"{profile.width}x{profile.height}, {profile.num_frames} frames")
            result = pipe(**kwargs)
            frames = self._normalize_frames(getattr(result, "frames", None))
            if cancel_event is not None and cancel_event.is_set():
                raise VideoGenerationCancelled("Đã dừng tạo video")
            output = self.workspace.new_output()
            enc = self._encode_mp4(frames, output, profile.duration, progress)
            try:
                peak = int(torch.cuda.max_memory_allocated())
                torch.cuda.reset_peak_memory_stats()
            except Exception:
                peak = None
        return {
            "file": output.name, "url": f"/api/ai-video/media/{output.name}", "mode": "text_to_video",
            "model": self.t2v_model, "model_type": mtype,
            "width": profile.width, "height": profile.height,
            "duration": profile.duration, "requested_fps": profile.fps, "actual_fps": enc["fps"],
            "frames": enc["frames"], "encoder": enc["encoder"], "seed": int(seed), "vram_peak_bytes": peak,
        }

    def generate_image(self, image_path: str | Path, prompt: str = "", *, quality="balanced", duration=3.0,
                       fps=16, seed=0, cancel_event=None, progress: ProgressCB | None = None) -> dict:
        """Image-to-video (or text+image-to-video) generation.

        Supports Wan 2.2 TI2V (takes both image and prompt), LTX-Video I2V,
        and SVD (image-only, prompt is metadata).
        """
        src = Path(image_path)
        if not src.exists():
            raise FileNotFoundError(src)
        mtype = _model_type(self.i2v_model)
        profile = _video_profile("image_to_video", quality, duration, fps, mtype)
        if progress: progress(5, "Nạp model ảnh thành video", self.i2v_model)
        with self._lock:
            pipe = self._load_i2v()
            torch = self._ensure_cuda()
            image = Image.open(src).convert("RGB")
            # Contain-fit to the model's working aspect without stretching.
            image.thumbnail((profile.width, profile.height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (profile.width, profile.height), (0, 0, 0))
            canvas.paste(image, ((profile.width-image.width)//2, (profile.height-image.height)//2))
            generator = torch.Generator(device="cuda").manual_seed(int(seed) if int(seed) >= 0 else 0)

            # Build model-specific kwargs
            kwargs = dict(
                num_frames=profile.num_frames, num_inference_steps=profile.steps,
                generator=generator,
            )

            if mtype == "wan":
                # Wan TI2V: accepts both image and prompt (true text+image→video)
                kwargs["image"] = canvas
                kwargs["prompt"] = prompt.strip() or "smooth natural motion, preserve character identity"
                kwargs["guidance_scale"] = profile.guidance
                kwargs["negative_prompt"] = (
                    "blurry, low quality, distorted, watermark, text, deformed, "
                    "bad anatomy, extra limbs, sudden scene change"
                )
            elif mtype == "ltx":
                # LTX I2V: accepts image, prompt, and resolution
                kwargs["image"] = canvas
                kwargs["prompt"] = prompt.strip() or "smooth natural motion"
                kwargs["width"] = profile.width
                kwargs["height"] = profile.height
                kwargs["guidance_scale"] = profile.guidance
            else:
                # SVD: image-only, prompt is metadata
                kwargs["image"] = canvas
                kwargs["decode_chunk_size"] = 8

            kwargs.update(self._progress_kwargs(pipe, cancel_event, progress, 10, 88))
            if progress: progress(10, "Đang tạo chuyển động", prompt.strip() or "Giữ nhân vật/ảnh gốc")
            result = pipe(**kwargs)
            frames = self._normalize_frames(getattr(result, "frames", None))
            if cancel_event is not None and cancel_event.is_set():
                raise VideoGenerationCancelled("Đã dừng tạo video")
            output = self.workspace.new_output()
            enc = self._encode_mp4(frames, output, profile.duration, progress)
            try:
                peak = int(torch.cuda.max_memory_allocated())
                torch.cuda.reset_peak_memory_stats()
            except Exception:
                peak = None
        # Build model-specific prompt note
        if mtype == "wan":
            prompt_note = "Wan TI2V: text+image → video; prompt controls motion direction."
        elif mtype == "ltx":
            prompt_note = "LTX-Video I2V: fast generation; prompt guides motion."
        else:
            prompt_note = "SVD preserves the input image; free-text motion prompt is metadata in this backend."
        return {
            "file": output.name, "url": f"/api/ai-video/media/{output.name}", "mode": "image_to_video",
            "model": self.i2v_model, "model_type": mtype,
            "width": profile.width, "height": profile.height,
            "duration": profile.duration, "requested_fps": profile.fps, "actual_fps": enc["fps"],
            "frames": enc["frames"], "encoder": enc["encoder"], "seed": int(seed),
            "prompt_note": prompt_note,
            "vram_peak_bytes": peak,
        }
