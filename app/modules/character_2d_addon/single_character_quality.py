from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image


def _load_rgb(source) -> Image.Image:
    if isinstance(source, (str, Path)):
        return Image.open(source).convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGB")
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    raise TypeError("Unsupported image source")


def inspect_single_character(source) -> dict:
    """Cheap layout gate for 'one centered character only'.

    It is intentionally conservative: it rejects images that place large
    foreground masses on both outer sides, a common symptom of groups/crowds.
    """
    with _load_rgb(source) as rgb:
        im = rgb.resize((256, 384), Image.Resampling.BILINEAR)
        arr = np.asarray(im, dtype=np.int16)

    h, w, _ = arr.shape
    patch = max(10, min(h, w) // 12)
    corners = np.concatenate([
        arr[:patch, :patch].reshape(-1, 3),
        arr[:patch, -patch:].reshape(-1, 3),
        arr[-patch:, :patch].reshape(-1, 3),
        arr[-patch:, -patch:].reshape(-1, 3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    mask = dist > 42.0

    # Ignore very top/bottom strips where shadows/ground often appear.
    band = mask[int(h * 0.06):int(h * 0.94), :]
    col = band.mean(axis=0)
    left_occ = float(band[:, :int(w * 0.23)].mean())
    center_occ = float(band[:, int(w * 0.27):int(w * 0.73)].mean())
    right_occ = float(band[:, int(w * 0.77):].mean())
    outer_occ = left_occ + right_occ

    # Count broad foreground column clusters.
    active = col > 0.12
    clusters = []
    start = None
    for i, on in enumerate(active):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= int(w * 0.07):
                clusters.append((start, i))
            start = None
    if start is not None and w - start >= int(w * 0.07):
        clusters.append((start, w))

    # A centered single character may have weapon/cape reach, but large masses
    # on both outer sides strongly suggest multiple people.
    side_group = left_occ > 0.28 and right_occ > 0.28
    too_many_clusters = len(clusters) >= 3
    center_missing = center_occ < 0.10
    ok = not side_group and not too_many_clusters and not center_missing

    score = 100.0
    score -= max(0.0, outer_occ - 0.42) * 95.0
    if too_many_clusters:
        score -= min(45.0, (len(clusters) - 2) * 18.0)
    if center_missing:
        score -= 45.0
    score = max(0.0, min(100.0, score))

    return {
        "ok": bool(ok),
        "score": round(score, 2),
        "left_occupancy": round(left_occ, 3),
        "center_occupancy": round(center_occ, 3),
        "right_occupancy": round(right_occ, 3),
        "foreground_clusters": len(clusters),
        "clusters": [list(x) for x in clusters],
    }
