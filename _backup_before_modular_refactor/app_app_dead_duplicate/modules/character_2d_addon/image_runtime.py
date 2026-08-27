from __future__ import annotations

from pathlib import Path
from threading import Lock
import io
import os
import random

from PIL import Image, ImageStat

STYLE = {
    "photo": "photorealistic natural lighting",
    "cartoon3d": "polished stylized 3D cartoon",
    "anime": "crisp anime game illustration",
    "cinematic": "cinematic fantasy game concept art",
    "illustration": "professional 2D game illustration, crisp readable shapes",
    "product": "clean studio product image",
    "fantasy": "high quality fantasy game character illustration, crisp line art",
}

BASE_MODEL = os.environ.get("AIVF_LIGHT_MODEL", "Lykon/dreamshaper-8")


def _target_size(size: str) -> tuple[int, int]:
    try:
        w, h = size.lower().split("x", 1)
        return int(w), int(h)
    except Exception:
        return (1024, 1024)


def _fit_multiple_64(w: int, h: int, max_side: int) -> tuple[int, int]:
    scale = min(1.0, max_side / max(w, h))
    nw = max(512, int(w * scale))
    nh = max(512, int(h * scale))
    nw = max(512, (nw // 64) * 64)
    nh = max(512, (nh // 64) * 64)
    return nw, nh


def generation_dimensions(size: str, quality: str = "high") -> tuple[int, int]:
    """Lightweight SD1.5-style internal render sizes.

    V10 keeps the requested export resolution but renders on a smaller latent
    canvas so first setup is lighter and inference is faster than the SDXL path.
    """
    w, h = _target_size(size)
    if quality == "fast":
        return _fit_multiple_64(w, h, 576)
    if quality == "medium":
        return _fit_multiple_64(w, h, 704)
    return _fit_multiple_64(w, h, 832)


def finalize_pil(image: Image.Image, size: str) -> bytes:
    target = _target_size(size)
    out = image.convert("RGB")
    if out.size != target:
        out = out.resize(target, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def image_bytes_are_blank(image_bytes: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            gray = im.convert("L").resize((64, 64))
            stat = ImageStat.Stat(gray)
            mean = float(stat.mean[0])
            contrast = float(stat.stddev[0])
        return (mean < 5.0 and contrast < 5.0) or (mean > 250.0 and contrast < 3.0)
    except Exception:
        return True




class SafetyBlockedOutput(RuntimeError):
    pass


def _result_was_safety_blocked(result) -> bool:
    flags = getattr(result, "nsfw_content_detected", None)
    if flags is None:
        return False
    if isinstance(flags, bool):
        return flags
    try:
        return any(bool(x) for x in flags)
    except Exception:
        return bool(flags)


def _checked_result_bytes(result, size: str) -> bytes:
    if _result_was_safety_blocked(result):
        raise SafetyBlockedOutput("safety_checker_blocked")
    if not getattr(result, "images", None):
        raise RuntimeError("image_pipeline_returned_no_images")
    data = finalize_pil(result.images[0], size)
    if image_bytes_are_blank(data):
        raise RuntimeError("blank_or_black_image_output")
    return data


class StandaloneLocalImageService:
    """Persistent lightweight local engine.

    Default model: DreamShaper 8 (SD1.5 family). On CUDA the runtime requests
    the fp16 variant to reduce transfer size and VRAM use versus the full model.
    Safety checking stays enabled; blank/blocked outputs are handled by the
    existing retry/quality-gate pipeline.
    """

    engine_name = "dreamshaper-8-fp16"

    def __init__(self, model_id: str | None, model_dir: str | Path):
        self.model_id = model_id or BASE_MODEL
        self.model_dir = Path(model_dir).resolve()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._text_pipe = None
        self._img_pipe = None
        self._lock = Lock()
        self._run_lock = Lock()
        self._device = None
        self._dtype = None

    @staticmethod
    def _runtime():
        try:
            import torch
        except ImportError as exc:
            raise ValueError("Thiếu torch trong Python hiện tại") from exc
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        if device == "cuda":
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
            except Exception:
                pass
        return torch, device, dtype

    @staticmethod
    def _generator(torch, device: str, seed: int | None):
        if seed is None:
            seed = random.SystemRandom().randint(1, 2_147_483_646)
        gen_device = "cuda" if device == "cuda" else "cpu"
        return torch.Generator(device=gen_device).manual_seed(int(seed)), int(seed)

    def _prepare_pipe(self, pipe, device: str):
        if device == "cuda":
            pipe.to(device)
            try:
                pipe.enable_attention_slicing()
            except Exception:
                pass
            try:
                pipe.enable_vae_slicing()
            except Exception:
                pass
            try:
                pipe.enable_vae_tiling()
            except Exception:
                pass
        else:
            pipe.to(device)
            try:
                pipe.enable_attention_slicing()
            except Exception:
                pass
        try:
            pipe.set_progress_bar_config(leave=False)
        except Exception:
            pass
        return pipe

    def _text_pipeline(self):
        if self._text_pipe is not None:
            return self._text_pipe
        with self._lock:
            if self._text_pipe is not None:
                return self._text_pipe
            try:
                from diffusers import AutoPipelineForText2Image, EulerAncestralDiscreteScheduler
            except ImportError as exc:
                raise ValueError(
                    "Thiếu thư viện image runtime. Hãy chạy SETUP_CHARACTER_2D_LIGHT.bat một lần."
                ) from exc

            torch, device, dtype = self._runtime()
            kwargs = {
                "torch_dtype": dtype,
                "cache_dir": str(self.model_dir),
            }
            if device == "cuda":
                kwargs["variant"] = "fp16"
            try:
                pipe = AutoPipelineForText2Image.from_pretrained(self.model_id, **kwargs)
                try:
                    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
                except Exception:
                    pass
            except Exception as exc:
                raise ValueError(
                    "Không nạp được model lightweight. Hãy chạy SETUP_CHARACTER_2D_LIGHT.bat rồi thử lại. "
                    f"Chi tiết: {exc}"
                ) from exc

            self._device = device
            self._dtype = dtype
            self._text_pipe = self._prepare_pipe(pipe, device)
            return self._text_pipe

    def _image_pipeline(self):
        if self._img_pipe is not None:
            return self._img_pipe
        text_pipe = self._text_pipeline()
        with self._lock:
            if self._img_pipe is not None:
                return self._img_pipe
            try:
                from diffusers import AutoPipelineForImage2Image
                pipe = AutoPipelineForImage2Image.from_pipe(text_pipe)
                self._img_pipe = self._prepare_pipe(pipe, self._device or "cpu")
                return self._img_pipe
            except Exception as exc:
                raise ValueError(f"Không tạo được lightweight img2img pipeline: {exc}") from exc

    @staticmethod
    def _steps(quality: str, edit: bool = False) -> int:
        if quality == "fast":
            return 8 if not edit else 10
        if quality == "medium":
            return 14 if not edit else 16
        return 20 if not edit else 18

    @staticmethod
    def _guidance(quality: str, edit: bool = False) -> float:
        if edit:
            return 5.0 if quality == "fast" else 6.0
        return 6.0 if quality == "fast" else 7.0

    def engine_info(self) -> dict:
        torch, device, _dtype = self._runtime()
        vram_gb = None
        if device == "cuda":
            try:
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 2)
            except Exception:
                pass
        return {
            "engine": self.engine_name,
            "base_model": self.model_id,
            "family": "sd15-lightweight",
            "recommended_flow": ["/character-2d/engine", "/character-2d/engine/warmup", "/character-2d/preview", "/character-2d/anchor"],
            "steps": {"fast": 8, "medium": 14, "high": 20},
            "device": device,
            "vram_gb": vram_gb,
            "loaded": self._text_pipe is not None,
        }

    def warmup(self) -> dict:
        self._text_pipeline()
        return self.engine_info()

    def generate(
        self,
        prompt: str,
        style: str = "fantasy",
        size: str = "1024x1536",
        quality: str = "high",
        *,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        pipe = self._text_pipeline()
        width, height = generation_dimensions(size, quality)
        steps = self._steps(quality)
        guidance = self._guidance(quality)
        torch, device, _dtype = self._runtime()
        generator, _seed = self._generator(torch, device, seed)
        prompt_text = f"{prompt}, {STYLE.get(style, STYLE['fantasy'])}"
        kwargs = dict(
            prompt=prompt_text,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=generator,
        )
        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt
        with self._run_lock, torch.inference_mode():
            result = pipe(**kwargs)
        return _checked_result_bytes(result, size)

    def edit(
        self,
        image_path: str | Path,
        prompt: str,
        style: str = "fantasy",
        size: str = "1024x1024",
        quality: str = "high",
        *,
        strength: float = 0.42,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        pipe = self._image_pipeline()
        width, height = generation_dimensions(size, quality)
        steps = self._steps(quality, edit=True)
        guidance = self._guidance(quality, edit=True)
        with Image.open(image_path) as source:
            init_image = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        torch, device, _dtype = self._runtime()
        generator, _seed = self._generator(torch, device, seed)
        strength = min(0.82, max(0.20, float(strength)))
        kwargs = dict(
            prompt=f"{prompt}, {STYLE.get(style, STYLE['fantasy'])}",
            image=init_image,
            strength=strength,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=generator,
        )
        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt
        with self._run_lock, torch.inference_mode():
            result = pipe(**kwargs)
        return _checked_result_bytes(result, size)
