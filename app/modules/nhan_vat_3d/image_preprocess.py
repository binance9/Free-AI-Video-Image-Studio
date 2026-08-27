"""Input image cleanup for better single-image 3D reconstruction."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def _corner_average(im: Image.Image) -> Tuple[int, int, int]:
    pts = [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]
    samples = [im.getpixel((max(0, x), max(0, y)))[:3] for x, y in pts]
    return tuple(int(sum(c[i] for c in samples) / len(samples)) for i in range(3))


def _remove_flat_background(im: Image.Image) -> Image.Image:
    """Cheap fallback background cleanup for plain/light backgrounds.

    Conservative rule: only remove pixels near the corner background color or
    near-white regions. This works best for clean product / character sheets.
    """
    rgba = im.convert("RGBA")
    bg = _corner_average(rgba)
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = px[x, y]
            near_bg = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 54
            near_white = r > 242 and g > 242 and b > 242
            if a > 0 and (near_bg or near_white):
                px[x, y] = (r, g, b, 0)
    alpha = rgba.getchannel("A").filter(ImageFilter.GaussianBlur(1.4))
    rgba.putalpha(alpha)
    return rgba


def _tight_bbox(im: Image.Image):
    alpha = im.getchannel("A")
    return alpha.point(lambda p: 255 if p > 8 else 0).getbbox()


def _safe_bbox(im: Image.Image):
    """Return bbox only when background removal likely succeeded.

    If the bbox covers nearly the whole frame, using it tends to create the
    "textured card / flat rectangle" failure mode on TripoSR, so we skip the
    crop and keep the original composition.
    """
    bbox = _tight_bbox(im)
    if not bbox:
        return None
    left, top, right, bottom = bbox
    bw = max(1, right - left)
    bh = max(1, bottom - top)
    area_ratio = (bw * bh) / max(1, im.width * im.height)
    full_w = bw / max(1, im.width)
    full_h = bh / max(1, im.height)
    if area_ratio > 0.88 or (full_w > 0.96 and full_h > 0.96):
        return None
    return bbox


def prepare_image_for_3d(src_path: str | Path, out_path: str | Path, canvas_size: int = 1024, vertical_bias: float = 0.54) -> Path:
    src_path = Path(src_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as raw:
        raw = ImageOps.exif_transpose(raw)
        original = raw.convert("RGBA")
        im = original.copy()

    # Background cleanup first.
    im = _remove_flat_background(im)
    bbox = _safe_bbox(im)

    if bbox:
        left, top, right, bottom = bbox
        pad_x = max(16, int((right - left) * 0.1))
        pad_y = max(16, int((bottom - top) * 0.1))
        crop = im.crop(
            (
                max(0, left - pad_x),
                max(0, top - pad_y),
                min(im.width, right + pad_x),
                min(im.height, bottom + pad_y),
            )
        )
    else:
        crop = im.copy()

    # IMPORTANT: preserve alpha from the cropped image before any RGB enhancement.
    alpha_mask = crop.getchannel("A")

    # Mild cleanup/enhancement: enough to help geometry/texture without making it fake.
    rgb = crop.convert("RGB")
    rgb = rgb.filter(ImageFilter.MedianFilter(3))
    rgb = ImageEnhance.Color(rgb).enhance(1.05)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.05)
    crop = rgb.convert("RGBA")
    crop.putalpha(alpha_mask)

    # Square transparent canvas. vertical_bias=0.54 (default, character use) leaves
    # a bit more room below for feet; do_vat_3d passes 0.5 for plain centering
    # since props (trees, houses...) have no "feet" composition assumption.
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    scale = min((canvas_size * 0.78) / max(1, crop.width), (canvas_size * 0.86) / max(1, crop.height))
    new_size = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
    crop = crop.resize(new_size, Image.Resampling.LANCZOS)
    x = (canvas_size - crop.width) // 2
    y = int(canvas_size * vertical_bias - crop.height / 2)
    y = max(0, min(canvas_size - crop.height, y))
    canvas.alpha_composite(crop, (x, y))

    # If the canvas ended up almost fully opaque, preprocessing likely failed.
    # Fall back to the original image resized onto a transparent canvas instead
    # of sending a flat textured rectangle into TripoSR.
    alpha = canvas.getchannel("A")
    alpha_bbox = alpha.point(lambda p: 255 if p > 8 else 0).getbbox()
    if alpha_bbox:
        aw = alpha_bbox[2] - alpha_bbox[0]
        ah = alpha_bbox[3] - alpha_bbox[1]
        area_ratio = (aw * ah) / max(1, canvas_size * canvas_size)
        if area_ratio > 0.92:
            plain = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            fallback = original.copy()
            scale = min((canvas_size * 0.82) / max(1, fallback.width), (canvas_size * 0.88) / max(1, fallback.height))
            new_size = (max(1, int(fallback.width * scale)), max(1, int(fallback.height * scale)))
            fallback = fallback.resize(new_size, Image.Resampling.LANCZOS)
            fx = (canvas_size - fallback.width) // 2
            fy = (canvas_size - fallback.height) // 2
            plain.alpha_composite(fallback, (fx, fy))
            canvas = plain

    canvas.save(out_path)
    return out_path
