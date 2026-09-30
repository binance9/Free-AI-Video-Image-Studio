from __future__ import annotations

from pathlib import Path
import colorsys
import re

import numpy as np
from PIL import Image


_COLOR_HUES = {
    "red": (0.0, 0.055),
    "burgundy": (0.98, 0.07),
    "crimson": (0.985, 0.065),
    "maroon": (0.985, 0.07),
    "gold": (0.115, 0.065),
    "orange": (0.075, 0.055),
    "green": (0.31, 0.11),
    "emerald": (0.37, 0.10),
    "blue": (0.61, 0.11),
    "navy": (0.63, 0.09),
    "purple": (0.77, 0.10),
    "cyan": (0.50, 0.09),
    "brown": (0.075, 0.07),
}


def detect_operation(prompt: str) -> str:
    p = " ".join((prompt or "").lower().split())
    recolor = (
        "change armor color", "change the armor color", "change armor colors", "change the armor colors",
        "change cape", "change the cape", "change color", "change the color", "recolor", "re-colour",
        "burgundy", "crimson", "maroon", "dark red", "red and gold", "đổi màu", "đổi màu sắc",
    )
    preserve = (
        "clean and refine", "clean & refine", "refine the reference", "improve sharpness", "improve detail",
        "keep everything the same", "same colors", "same design", "same proportions", "giữ nguyên", "làm nét",
        "tăng độ nét",
    )
    if any(x in p for x in recolor):
        return "recolor-reference"
    if any(x in p for x in preserve):
        return "preserve-refine"

    # "create based on reference" without any requested transformation is
    # effectively a clone/cleanup request. Do not needlessly diffuse it.
    clone_phrases = (
        "based on the reference", "based on reference", "from the reference", "using the reference",
        "theo ảnh mẫu", "dựa trên ảnh mẫu", "giống ảnh mẫu",
    )
    edit_verbs = (
        "change ", "replace ", "remove ", "add ", "turn into", "convert ", "different ",
        "đổi ", "thay ", "xóa ", "xoá ", "thêm ",
    )
    if any(x in p for x in clone_phrases) and not any(x in p for x in edit_verbs):
        return "preserve-refine"
    return "reference-edit"


def _hue_distance(h: np.ndarray, target: float) -> np.ndarray:
    d = np.abs(h - target)
    return np.minimum(d, 1.0 - d)


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def _family_ratio(h: np.ndarray, s: np.ndarray, v: np.ndarray, name: str) -> float:
    name = (name or "").lower().strip()
    aliases = {"dark_red": "red", "burgundy_red": "red", "grey": "gray"}
    name = aliases.get(name, name)
    chroma = (s >= 0.30) & (v >= 0.11) & (v <= 0.98)
    denom = int(chroma.sum())
    if denom <= 0:
        return 0.0
    if name in {"black", "gray", "silver", "white"}:
        if name == "black": mask = (v < 0.22) & (s < 0.45)
        elif name == "white": mask = (v > 0.78) & (s < 0.24)
        elif name == "silver": mask = (v > 0.42) & (v < 0.86) & (s < 0.22)
        else: mask = (v > 0.25) & (v < 0.78) & (s < 0.22)
        return float(mask.sum()) / float(mask.size)
    target = _COLOR_HUES.get(name)
    if target is None:
        return 0.0
    center, width = target
    mask = chroma & (_hue_distance(h, center) <= width)
    return float(mask.sum()) / float(denom)


def target_palette_score(image_path: str | Path, spec) -> dict:
    with Image.open(image_path).convert("RGB") as im:
        arr = np.asarray(im)
    h, s, v = _rgb_to_hsv(arr)

    requested: list[tuple[str, str, float]] = []
    if getattr(spec, "armor_primary", None): requested.append(("armor_primary", spec.armor_primary, 0.18))
    if getattr(spec, "accent_color", None): requested.append(("accent_color", spec.accent_color, 0.045))
    if getattr(spec, "cape_color", None): requested.append(("cape_color", spec.cape_color, 0.10))

    parts = []
    for field, color, target_ratio in requested:
        ratio = _family_ratio(h, s, v, color)
        score = max(0.0, min(1.0, ratio / max(target_ratio, 1e-6)))
        parts.append({"field": field, "color": color, "ratio": round(ratio, 4), "score": round(score, 4)})

    if not parts:
        return {"ok": True, "score": 1.0, "parts": [], "reason": "no_target_palette_requested"}

    # Primary armor matters most; cape and accent are supporting evidence.
    weights = {"armor_primary": 0.55, "accent_color": 0.20, "cape_color": 0.25}
    denom = sum(weights.get(x["field"], 0.2) for x in parts)
    score = sum(x["score"] * weights.get(x["field"], 0.2) for x in parts) / max(denom, 1e-6)
    return {"ok": score >= 0.52, "score": round(score, 4), "parts": parts, "threshold": 0.52}


def _check_score(validation: dict, names: set[str]) -> float:
    checks = validation.get("attributes", {}).get("checks", [])
    vals = []
    for row in checks:
        if row.get("check") not in names:
            continue
        if row.get("ok") is True:
            vals.append(1.0)
        elif row.get("ok") is False:
            vals.append(0.0)
        else:
            vals.append(0.55)
    return sum(vals) / len(vals) if vals else 1.0


def build_recolor_gate(validation: dict, similarity: dict, palette: dict, min_score: int) -> dict:
    base = validation.get("base", {})
    attrs = validation.get("attributes", {})
    base_score = float(base.get("quality_score", 0.0)) / 100.0
    raw_identity = similarity.get("similarity")
    # A missing CLIP score must never become an automatic 0% identity failure.
    # The reference similarity helper already provides a grayscale/edge fallback;
    # if even that is unavailable, use a conservative neutral score and let the
    # structural/weapon/palette gates decide.
    identity = float(raw_identity) if raw_identity is not None else 0.66
    weapon = _check_score(validation, {"weapon_type", "weapon_family", "weapon_count"})
    identity_attr = _check_score(validation, {"gender", "single_character", "compact_proportions"})
    target_color = float(palette.get("score", 0.0))

    # Color similarity to the original reference is intentionally NOT part of this score.
    final = (
        identity * 0.28 +
        base_score * 0.24 +
        weapon * 0.18 +
        identity_attr * 0.10 +
        target_color * 0.20
    )

    structural_issues = {
        "blank", "too_dark", "too_flat", "mostly_black", "too_little_visible_content",
        "face", "fullbody", "background", "multiple_characters", "compact_composition",
    }
    blockers = [x for x in base.get("issues", []) if x in structural_issues]
    hard = set(attrs.get("hard_failures", []))
    # Attribute CLIP color checks are deliberately ignored for recolor jobs;
    # the deterministic target-palette check above is the authority for colors.
    # Relaxed: removed plain_background, compact_proportions, no_pedestal from
    # the critical blockers list.  These CLIP checks are unreliable and cause
    # false rejects on good images.  Gender and weapon checks stay critical.
    for name in ("gender", "weapon_type", "weapon_family", "weapon_count", "single_character"):
        if name in hard and name not in blockers:
            blockers.append(name)
    if raw_identity is not None and identity < 0.54:
        blockers.append("reference_identity_drift")
    if not palette.get("ok"):
        blockers.append("target_palette_not_reached")

    threshold = max(0.68, min(0.76, float(min_score) / 100.0))
    blockers = list(dict.fromkeys(blockers))

    # Final export bridge: a recolor that is overwhelmingly correct must not be
    # rejected by stale/legacy attribute blockers. This is intentionally strict:
    # identity, weapon and target palette all have to be strong. Only genuine
    # render-structure failures remain fatal in this high-confidence path.
    critical_render = {
        "blank", "too_dark", "too_flat", "mostly_black",
        "too_little_visible_content", "multiple_characters",
    }
    strong_recolor = bool(
        final >= max(0.86, threshold)
        and identity >= 0.82
        and weapon >= 0.85
        and target_color >= 0.80
        and base_score >= 0.62
    )
    if strong_recolor:
        blockers = [b for b in blockers if b in critical_render]
    accepted = bool(final >= threshold and not blockers)
    debug = {
        "operation": "recolor-reference",
        "identity_similarity": round(identity, 4),
        "base_quality": round(base_score, 4),
        "weapon_score": round(weapon, 4),
        "identity_attribute_score": round(identity_attr, 4),
        "target_color_score": round(target_color, 4),
        "final_score": round(final, 4),
        "pass_threshold": round(threshold, 4),
        "ignored_original_color_similarity": True,
        "high_confidence_export_override": strong_recolor,
        "palette": palette,
    }
    return {
        "accepted": accepted,
        "blockers": blockers,
        "uncertain": attrs.get("uncertain", []),
        "quality_score": round(final * 100.0, 1),
        "minimum_score": round(threshold * 100.0, 1),
        "strict_attribute_gate": True,
        "operation_aware_gate": True,
        "gate_debug": debug,
    }
