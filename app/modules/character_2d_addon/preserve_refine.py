from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


def refine_reference_image(source_path: str | Path, output_path: str | Path) -> dict:
    """Gently refine a reference without redesigning or recoloring it.

    This path is intentionally deterministic: no diffusion, no palette transfer,
    no geometry changes. It is used for requests such as "clean/refine, keep the
    same design/colors" where the uploaded reference itself is the source of truth.
    """
    src = Path(source_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src).convert("RGB") as im:
        # Very small detail lift only. Keep colors and layout visually identical.
        refined = ImageEnhance.Sharpness(im).enhance(1.08)
        refined = refined.filter(ImageFilter.UnsharpMask(radius=1.0, percent=65, threshold=4))
        refined.save(out, "PNG")

    return {
        "ok": True,
        "mode": "preserve-refine",
        "source": str(src),
        "output": str(out),
        "diffusion_used": False,
        "palette_changed": False,
    }
