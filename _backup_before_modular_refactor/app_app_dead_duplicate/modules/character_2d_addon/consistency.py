from __future__ import annotations

from pathlib import Path
from PIL import Image


def histogram_similarity(path_a: str | Path, path_b: str | Path) -> float:
    with Image.open(path_a) as a, Image.open(path_b) as b:
        a = a.convert("RGB").resize((256, 256))
        b = b.convert("RGB").resize((256, 256))
        ha = a.histogram()
        hb = b.histogram()
    diff = sum(abs(x - y) for x, y in zip(ha, hb))
    total = max(1, sum(ha))
    similarity = max(0.0, 1.0 - (diff / (2 * total)))
    return round(similarity, 4)
