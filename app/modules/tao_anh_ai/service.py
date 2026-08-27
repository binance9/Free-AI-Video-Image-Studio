"""Free local text-to-image and image-to-image service using Diffusers."""
from __future__ import annotations

from pathlib import Path
from threading import Lock
import inspect

from app.core.shared_services import JobCancelled

from PIL import Image

from .upscale import finalize_pil, generation_dimensions

_STYLE = {
    "photo": "photorealistic, natural lighting, detailed materials, professional photography",
    "cartoon3d": "polished 3D cartoon, clean shapes, expressive, cinematic soft lighting",
    "anime": "anime illustration, crisp line art, detailed lighting, clean composition",
    "cinematic": "cinematic concept art, dramatic light, strong composition, detailed atmosphere",
    "illustration": "professional digital illustration, refined colors, clean composition",
    "product": "professional product image, accurate proportions, clean studio lighting",
    "fantasy": "high-detail fantasy illustration, cinematic lighting, rich environment",
}


class LocalImageService:
    def __init__(self, model_id: str, model_dir: str | Path):
        self.model_id = model_id
        self.model_dir = Path(model_dir).resolve()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._text_pipe = None
        self._img_pipe = None
        self._lock = Lock()
        self._run_lock = Lock()

    def generate(self, prompt: str, style: str = "photo", size: str = "1536x1024", quality: str = "high", *, cancel_event=None, progress=None) -> bytes:
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("Đã dừng tạo ảnh")
        pipe = self._text_pipeline()
        width, height = generation_dimensions(size)
        steps = 20 if quality == "high" else 12
        kwargs = dict(prompt=self._prompt(prompt, style), width=width, height=height, num_inference_steps=steps, guidance_scale=7.0)
        self._attach_cancel_callback(pipe, kwargs, steps, cancel_event, progress)
        with self._run_lock:
            result = pipe(**kwargs)
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("Đã dừng tạo ảnh")
        return finalize_pil(result.images[0], size)

    def edit(self, image_path: str | Path, prompt: str, style: str = "photo", size: str = "1536x1024", quality: str = "high", *, cancel_event=None, progress=None) -> bytes:
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("Đã dừng sửa ảnh")
        pipe = self._image_pipeline()
        width, height = generation_dimensions(size)
        with Image.open(image_path) as source:
            init_image = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        steps = 24 if quality == "high" else 14
        kwargs = dict(prompt=self._prompt(prompt, style), image=init_image, strength=0.58, num_inference_steps=steps, guidance_scale=7.0)
        self._attach_cancel_callback(pipe, kwargs, steps, cancel_event, progress)
        with self._run_lock:
            result = pipe(**kwargs)
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("Đã dừng sửa ảnh")
        return finalize_pil(result.images[0], size)


    @staticmethod
    def _attach_cancel_callback(pipe, kwargs: dict, steps: int, cancel_event, progress) -> None:
        params = inspect.signature(pipe.__call__).parameters
        if "callback_on_step_end" not in params:
            return
        def callback(_pipe, step_index, _timestep, callback_kwargs):
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled("Đã dừng AI ảnh theo yêu cầu")
            if progress:
                pct = 35 + int(((int(step_index) + 1) / max(1, int(steps))) * 60)
                progress(min(95, pct), "Đang tạo ảnh AI", f"Bước {int(step_index)+1}/{steps}")
            return callback_kwargs
        kwargs["callback_on_step_end"] = callback

    def _runtime(self):
        try:
            import torch
        except ImportError as exc:
            raise ValueError("Chưa cài AI local. Chạy SETUP_FREE_AI.bat một lần.") from exc
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        return torch, device, dtype

    def _text_pipeline(self):
        if self._text_pipe is not None:
            return self._text_pipe
        with self._lock:
            if self._text_pipe is not None:
                return self._text_pipe
            try:
                from diffusers import AutoPipelineForText2Image
            except ImportError as exc:
                raise ValueError("Chưa cài Diffusers local. Chạy SETUP_FREE_AI.bat.") from exc
            torch, device, dtype = self._runtime()
            kwargs = {"torch_dtype": dtype, "cache_dir": str(self.model_dir)}
            self._text_pipe = AutoPipelineForText2Image.from_pretrained(self.model_id, **kwargs)
            self._text_pipe.to(device)
            if device == "cpu":
                self._text_pipe.enable_attention_slicing()
            return self._text_pipe

    def _image_pipeline(self):
        if self._img_pipe is not None:
            return self._img_pipe
        with self._lock:
            if self._img_pipe is not None:
                return self._img_pipe
            try:
                from diffusers import AutoPipelineForImage2Image
            except ImportError as exc:
                raise ValueError("Chưa cài Diffusers local. Chạy SETUP_FREE_AI.bat.") from exc
            torch, device, dtype = self._runtime()
            self._img_pipe = AutoPipelineForImage2Image.from_pretrained(
                self.model_id, torch_dtype=dtype, cache_dir=str(self.model_dir)
            )
            self._img_pipe.to(device)
            if device == "cpu":
                self._img_pipe.enable_attention_slicing()
            return self._img_pipe

    @staticmethod
    def _prompt(prompt: str, style: str) -> str:
        clean = (prompt or "").strip()
        if len(clean) < 3:
            raise ValueError("Mô tả ảnh quá ngắn")
        return f"{clean}. Style: {_STYLE.get(style, _STYLE['photo'])}. polished, high detail, suitable for video editing"
