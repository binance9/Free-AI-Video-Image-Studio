from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter, ImageStat


def inspect_face_region(image_path: str | Path) -> dict:
    path = Path(image_path)
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        crop = rgb.crop((int(w * 0.28), int(h * 0.05), int(w * 0.72), int(h * 0.38)))
        gray = crop.convert("L")
        contrast = ImageStat.Stat(gray).stddev[0]
        mean = ImageStat.Stat(gray).mean[0]
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_score = ImageStat.Stat(edges).mean[0]
    score = round((contrast * 0.5) + (edge_score * 1.2), 2)
    ok = score >= 28 and 40 <= mean <= 215
    return {
        "ok": ok,
        "score": score,
        "contrast": round(float(contrast), 2),
        "edge_score": round(float(edge_score), 2),
        "brightness": round(float(mean), 2),
    }
