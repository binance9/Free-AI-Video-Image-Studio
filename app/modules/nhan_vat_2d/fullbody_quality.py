from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter, ImageStat


def _edge_mean(region: Image.Image) -> float:
    gray = region.convert("L")
    return float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0])


def inspect_fullbody(image_path: str | Path) -> dict:
    """Cheap framing check: a full-body sprite should contain visible detail in the lower body/feet area."""
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        lower = rgb.crop((int(w * 0.15), int(h * 0.68), int(w * 0.85), int(h * 0.97)))
        feet = rgb.crop((int(w * 0.18), int(h * 0.82), int(w * 0.82), int(h * 0.99)))
        mid = rgb.crop((int(w * 0.12), int(h * 0.35), int(w * 0.88), int(h * 0.68)))
        lower_contrast = float(ImageStat.Stat(lower.convert("L")).stddev[0])
        feet_contrast = float(ImageStat.Stat(feet.convert("L")).stddev[0])
        lower_edges = _edge_mean(lower)
        feet_edges = _edge_mean(feet)
        mid_edges = _edge_mean(mid)

    # Relaxed: score threshold 20->15 and ratio 0.16->0.10.  Many good
    # full-body renders with stylized 2D art (less edge detail in feet area)
    # were wrongly rejected.  The real signal for "no body" is a near-zero
    # score, not a borderline one.
    score = (lower_contrast * 0.35) + (feet_contrast * 0.25) + (lower_edges * 1.1) + (feet_edges * 1.4)
    ratio = feet_edges / max(0.1, mid_edges)
    ok = score >= 15.0 and ratio >= 0.10
    return {
        "ok": bool(ok),
        "score": round(score, 2),
        "lower_contrast": round(lower_contrast, 2),
        "feet_contrast": round(feet_contrast, 2),
        "lower_edge": round(lower_edges, 2),
        "feet_edge": round(feet_edges, 2),
        "feet_to_mid_edge_ratio": round(ratio, 3),
    }
