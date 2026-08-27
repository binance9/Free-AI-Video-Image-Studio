from __future__ import annotations

from pathlib import Path
import colorsys
import numpy as np
from PIL import Image

# Target display hues. Values are intentionally game-art friendly rather than photorealistic.
TARGET_RGB = {
    "red": (150, 24, 38),       # burgundy/deep red
    "blue": (35, 92, 185),
    "green": (43, 125, 55),
    "purple": (112, 54, 168),
    "gold": (205, 150, 34),
    "black": (35, 35, 42),
    "white": (225, 225, 230),
    "silver": (165, 172, 185),
    "brown": (105, 66, 40),
    "gray": (110, 115, 125),
    "cyan": (30, 160, 190),
}


def _rgb_to_hsv_np(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = rgb.astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(axis=-1)
    mn = arr.min(axis=-1)
    diff = mx - mn
    h = np.zeros_like(mx)
    nz = diff > 1e-6
    idx = nz & (mx == r)
    h[idx] = ((g[idx] - b[idx]) / diff[idx]) % 6
    idx = nz & (mx == g)
    h[idx] = (b[idx] - r[idx]) / diff[idx] + 2
    idx = nz & (mx == b)
    h[idx] = (r[idx] - g[idx]) / diff[idx] + 4
    h = (h / 6.0) % 1.0
    s = np.where(mx <= 1e-6, 0.0, diff / np.maximum(mx, 1e-6))
    return h, s, mx


def _hue_distance(a: np.ndarray, b: float) -> np.ndarray:
    d = np.abs(a - b)
    return np.minimum(d, 1.0 - d)


def _target_hsv(name: str) -> tuple[float, float, float]:
    rgb = TARGET_RGB.get(name, TARGET_RGB["red"])
    return colorsys.rgb_to_hsv(*(v / 255.0 for v in rgb))


def _dominant_material_hue(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> float | None:
    # Ignore gray background, skin/hair shadows, and gold trim. We want the dominant colored garment hue.
    mask = (s > 0.28) & (v > 0.15) & (v < 0.98)
    if int(mask.sum()) < 150:
        return None
    values = h[mask]
    bins = np.linspace(0.0, 1.0, 73)
    hist, edges = np.histogram(values, bins=bins)

    # Exclude orange/yellow/gold and skin-like hues so existing gold trim/hair are preserved.
    centers = (edges[:-1] + edges[1:]) * 0.5
    exclude = ((centers >= 0.02) & (centers <= 0.18))
    hist = hist.copy()
    hist[exclude] = 0
    if hist.max() <= 0:
        return None
    return float(centers[int(hist.argmax())])


def recolor_materials(source_path: str | Path, output_path: str | Path, spec) -> dict:
    """Deterministically recolor the dominant garment material while preserving geometry.

    This is used before diffusion for pure recolor requests. It avoids asking img2img to both
    preserve identity and perform a large palette swap at the same time.
    """
    src = Path(source_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src).convert("RGBA") as im:
        arr = np.array(im)

    rgb = arr[..., :3]
    alpha = arr[..., 3]
    h, s, v = _rgb_to_hsv_np(rgb)
    dominant = _dominant_material_hue(h, s, v)
    target_name = getattr(spec, "armor_primary", None) or getattr(spec, "cape_color", None)
    if dominant is None or not target_name or target_name not in TARGET_RGB:
        with Image.fromarray(arr, "RGBA") as im:
            im.save(out, "PNG")
        return {"ok": False, "output": str(out), "reason": "no_recolorable_material", "target": target_name}

    th, ts, tv = _target_hsv(target_name)
    # Broad enough to catch shaded/highlighted versions of the same garment color,
    # while preserving gold trim, blonde hair and neutral armor parts.
    material = (_hue_distance(h, dominant) <= 0.105) & (s >= 0.20) & (alpha > 8)

    # Preserve very bright near-white highlights and very dark outline pixels.
    material &= (v >= 0.12) & (v <= 0.97)

    # Build RGB using target hue while keeping original lightness/shading.
    out_rgb = rgb.copy().astype(np.uint8)
    idxs = np.argwhere(material)
    if len(idxs):
        # Keep per-pixel value; use strong target saturation so the new color is unmistakable.
        for y, x in idxs:
            vv = float(np.clip(v[y, x] * (0.86 + 0.14 * tv), 0.10, 0.94))
            ss = float(np.clip(max(s[y, x], ts * 0.82), 0.38, 0.96))
            rr, gg, bb = colorsys.hsv_to_rgb(th, ss, vv)
            out_rgb[y, x] = (int(rr * 255), int(gg * 255), int(bb * 255))

    out_arr = np.dstack([out_rgb, alpha])
    Image.fromarray(out_arr.astype(np.uint8), "RGBA").save(out, "PNG")

    changed_ratio = float(material.sum()) / float(material.size)
    return {
        "ok": bool(changed_ratio >= 0.01),
        "output": str(out),
        "target": target_name,
        "dominant_source_hue": round(dominant, 4),
        "changed_ratio": round(changed_ratio, 4),
    }
