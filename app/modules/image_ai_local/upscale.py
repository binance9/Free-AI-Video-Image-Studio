"""Local image sizing helpers; no paid API is used."""
from __future__ import annotations

import io
from PIL import Image, ImageOps

_TARGET_SIZES = {
    "1024x1024": (1024, 1024),
    "1536x1024": (1536, 1024),
    "1024x1536": (1024, 1536),
    "2048x1152": (2048, 1152),
    "2048x2048": (2048, 2048),
    "3840x2160": (3840, 2160),
    "2160x3840": (2160, 3840),
}


def target_dimensions(target_size: str) -> tuple[int, int]:
    dims = _TARGET_SIZES.get(target_size)
    if not dims:
        raise ValueError("Kích thước AI ảnh không hợp lệ")
    return dims


def generation_dimensions(target_size: str) -> tuple[int, int]:
    """Keep SD 1.5 generation light, then finish to requested HD size locally."""
    width, height = target_dimensions(target_size)
    if width == height:
        return 512, 512
    return (640, 384) if width > height else (384, 640)


def finalize_pil(image: Image.Image, target_size: str) -> bytes:
    dims = target_dimensions(target_size)
    image = ImageOps.fit(image.convert("RGB"), dims, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()
