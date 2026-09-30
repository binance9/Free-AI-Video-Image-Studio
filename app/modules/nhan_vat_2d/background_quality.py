from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter, ImageStat


def _edge_mean(region: Image.Image) -> float:
    gray = region.convert("L")
    return float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0])


def inspect_background(image_path: str | Path) -> dict:
    """Approximate whether the background is too busy for sprite-sheet use.
    Checks corner complexity versus center complexity.
    """
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        corners = [
            rgb.crop((0, 0, int(w * 0.22), int(h * 0.22))),
            rgb.crop((int(w * 0.78), 0, w, int(h * 0.22))),
            rgb.crop((0, int(h * 0.78), int(w * 0.22), h)),
            rgb.crop((int(w * 0.78), int(h * 0.78), w, h)),
        ]
        center = rgb.crop((int(w * 0.3), int(h * 0.18), int(w * 0.7), int(h * 0.82)))
        corner_edges = sum(_edge_mean(c) for c in corners) / max(1, len(corners))
        center_edges = _edge_mean(center)
        corner_contrast = sum(ImageStat.Stat(c.convert("L")).stddev[0] for c in corners) / max(1, len(corners))
    clutter_ratio = corner_edges / max(1.0, center_edges)
    plain_canvas = corner_edges < 12.0 and corner_contrast < 10.0
    # Relaxed: a plain white/gray background should pass even when the character
    # has high edge detail in center (center_edges can be high for a well-drawn
    # character).  The real signal for "bad background" is corner clutter and
    # corner contrast, NOT center detail.  Raise corner_edges threshold 28->38,
    # clutter_ratio 0.62->0.85, corner_contrast 58->72.
    ok = plain_canvas or (corner_edges < 38.0 and clutter_ratio < 0.85 and corner_contrast < 72.0)
    penalty_ratio = 0.0 if plain_canvas else clutter_ratio * 15.0
    score = max(0.0, 100.0 - (corner_edges * 1.6 + corner_contrast * 0.5 + penalty_ratio))
    return {
        "ok": bool(ok),
        "score": round(score, 2),
        "corner_edge": round(corner_edges, 2),
        "center_edge": round(center_edges, 2),
        "corner_contrast": round(corner_contrast, 2),
        "clutter_ratio": round(clutter_ratio, 3),
    }
