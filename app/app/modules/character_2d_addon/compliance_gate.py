from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .command_spec import CommandSpec

_CANON = {
    "black": np.array([25, 25, 25], dtype=np.float32),
    "white": np.array([238, 238, 238], dtype=np.float32),
    "silver": np.array([185, 190, 198], dtype=np.float32),
    "gray": np.array([145, 145, 150], dtype=np.float32),
    "red": np.array([180, 45, 45], dtype=np.float32),
    "blue": np.array([45, 85, 190], dtype=np.float32),
    "cyan": np.array([55, 175, 200], dtype=np.float32),
    "green": np.array([55, 135, 65], dtype=np.float32),
    "purple": np.array([105, 55, 155], dtype=np.float32),
    "gold": np.array([190, 145, 45], dtype=np.float32),
    "brown": np.array([105, 70, 45], dtype=np.float32),
}


def _load(source: str | Path | bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(source, (str, Path)):
        return Image.open(source).convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGB")
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    raise TypeError("Unsupported image source")


def _foreground(rgb: Image.Image) -> np.ndarray:
    im = rgb.resize((256, 384), Image.Resampling.BILINEAR)
    arr = np.asarray(im, dtype=np.float32)
    h, w, _ = arr.shape
    p = max(10, min(h, w) // 12)
    corners = np.concatenate([
        arr[:p, :p].reshape(-1, 3), arr[:p, -p:].reshape(-1, 3),
        arr[-p:, :p].reshape(-1, 3), arr[-p:, -p:].reshape(-1, 3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    # Central/character-biased region to avoid background color dominating.
    mask = dist > 36.0
    mask[:, :int(w * 0.08)] = False
    mask[:, int(w * 0.92):] = False
    return arr[mask]


def _color_fraction(pixels: np.ndarray, color: str) -> float:
    if pixels.size == 0 or color not in _CANON:
        return 0.0
    ref = _CANON[color]
    dist = np.sqrt(((pixels - ref) ** 2).sum(axis=1))
    threshold = 95.0 if color in {"silver", "gray", "white", "black"} else 82.0
    return float((dist < threshold).mean())


def _weapon_geometry(rgb: Image.Image, spec: CommandSpec) -> dict[str, Any]:
    if spec.weapon_type not in {"sword", "katana", "blade", "spear"} or not spec.weapon_count:
        return {"checked": False, "ok": True, "score": 100.0, "reason": "not_requested"}
    try:
        import cv2
    except Exception:
        return {"checked": False, "ok": True, "score": 70.0, "reason": "opencv_unavailable"}

    arr = np.asarray(rgb.resize((256, 384), Image.Resampling.BILINEAR).convert("L"))
    edges = cv2.Canny(arr, 70, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=28, minLineLength=62, maxLineGap=12)
    if lines is None:
        return {"checked": True, "ok": False, "score": 15.0, "left": 0, "right": 0}

    left = right = 0
    h, w = arr.shape
    accepted = []
    for x1, y1, x2, y2 in lines[:, 0]:
        length = float(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        if length < h * 0.16:
            continue
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        # Ignore face/hair horizontals and ground-shadow lines.
        if my < h * 0.24 or my > h * 0.96:
            continue
        if abs(x2 - x1) > abs(y2 - y1) * 2.8:
            continue
        if mx < w * 0.46:
            left += 1
        elif mx > w * 0.54:
            right += 1
        accepted.append([int(x1), int(y1), int(x2), int(y2)])

    if spec.weapon_count == 1:
        ok = (left + right) >= 1
        score = 100.0 if ok else 25.0
    else:
        ok = left >= 1 and right >= 1
        score = 100.0 if ok else (58.0 if (left + right) >= 1 else 20.0)
    return {
        "checked": True, "ok": bool(ok), "score": score,
        "left": int(left), "right": int(right), "lines": accepted[:12],
    }


def evaluate_command_compliance(source, spec: CommandSpec) -> dict:
    with _load(source) as rgb:
        pixels = _foreground(rgb)
        palette_checks = []
        requested = []
        if spec.hair_color:
            requested.append(("hair_color", spec.hair_color, 0.010))
        if spec.armor_color:
            requested.append(("armor_color", spec.armor_color, 0.018))
        for c in spec.cloth_colors[:2]:
            requested.append(("cloth_color", c, 0.012))

        for role, color, minimum in requested:
            frac = _color_fraction(pixels, color)
            palette_checks.append({
                "role": role, "color": color, "fraction": round(frac, 4),
                "minimum": minimum, "ok": bool(frac >= minimum),
            })

        weapon = _weapon_geometry(rgb, spec)

    checks = []
    checks.extend(palette_checks)
    if weapon.get("checked"):
        checks.append({"role": "weapon_geometry", "ok": weapon.get("ok", False)})

    if not checks:
        score = 100.0
    else:
        color_scores = [100.0 if c["ok"] else max(20.0, min(80.0, c.get("fraction", 0) * 4000.0)) for c in palette_checks]
        parts = color_scores + ([float(weapon.get("score", 100.0))] if weapon.get("checked") else [])
        score = round(sum(parts) / max(1, len(parts)), 1)

    issues = []
    for c in palette_checks:
        if not c["ok"]:
            issues.append(f"missing_{c['role']}:{c['color']}")
    if weapon.get("checked") and not weapon.get("ok"):
        issues.append("weapon_lock")

    passed = all(c.get("ok", True) for c in checks) if checks else True
    return {
        "passed": bool(passed),
        "score": score,
        "issues": issues,
        "palette": palette_checks,
        "weapon": weapon,
    }
