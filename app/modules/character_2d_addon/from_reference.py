from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps
import io

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def normalize_reference_bytes(data: bytes, filename: str, out_path: str | Path, canvas: int = 1024) -> Path:
    suffix = Path(filename or "reference.png").suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Reference must be PNG, JPG, JPEG or WEBP")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            src = im.convert("RGB")
    except Exception as exc:
        raise ValueError(f"Invalid reference image: {exc}") from exc

    # Preserve full character and proportions; only fit/pad, never crop.
    margin = int(canvas * 0.08)
    max_side = canvas - margin * 2
    fitted = ImageOps.contain(src, (max_side, max_side), Image.Resampling.LANCZOS)
    bg = Image.new("RGB", (canvas, canvas), (232, 232, 232))
    x = (canvas - fitted.width) // 2
    y = (canvas - fitted.height) // 2
    bg.paste(fitted, (x, y))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, "PNG")
    return out
