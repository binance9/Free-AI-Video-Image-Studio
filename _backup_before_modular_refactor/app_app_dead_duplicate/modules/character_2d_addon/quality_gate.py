from __future__ import annotations

from pathlib import Path
from .face_quality import inspect_face_region
from .fullbody_quality import inspect_fullbody
from .background_quality import inspect_background
from .single_character_quality import inspect_single_character


def _global_image_check(image_path: str | Path) -> dict:
    from .output_guard import inspect_image

    report = inspect_image(image_path)
    issues = list(report.get("issues", []))
    return {
        "ok": bool(report.get("ok")),
        "brightness": float(report.get("brightness", 0.0)),
        "contrast": float(report.get("contrast", 0.0)),
        "blank": bool(not report.get("ok")),
        "visible_ratio": float(report.get("visible_ratio", 0.0)),
        "non_black_ratio": float(report.get("non_black_ratio", 0.0)),
        "unique_colors": int(report.get("unique_colors", 0)),
        "reason": report.get("reason", "unknown"),
        "issues": issues,
    }


def evaluate_anchor(image_path: str | Path, *, min_score: int = 72) -> dict:
    face = inspect_face_region(image_path)
    fullbody = inspect_fullbody(image_path)
    background = inspect_background(image_path)
    single = inspect_single_character(image_path)
    image = _global_image_check(image_path)

    face_score = min(100.0, max(0.0, float(face.get("score", 0)) * 1.65))
    body_score = min(100.0, max(0.0, float(fullbody.get("score", 0)) * 3.0))
    bg_score = min(100.0, max(0.0, float(background.get("score", 0))))
    single_score = min(100.0, max(0.0, float(single.get("score", 0))))
    image_score = 100.0 if image["ok"] else 0.0
    score = round(face_score * 0.31 + body_score * 0.29 + bg_score * 0.11 + single_score * 0.16 + image_score * 0.13, 1)

    issues = []
    if not image["ok"]:
        issues.append("blank")
        issues.extend([x for x in image.get("issues", []) if x not in issues])
    if not face.get("ok"):
        issues.append("face")
    if not fullbody.get("ok"):
        issues.append("fullbody")
    if not background.get("ok"):
        issues.append("background")
    if not single.get("ok"):
        issues.append("multiple_characters")
    if image.get("brightness", 100) < 35:
        issues.append("dark")

    passed = bool(
        image["ok"] and face.get("ok") and fullbody.get("ok")
        and background.get("ok") and single.get("ok")
        and score >= min_score
    )
    return {
        "passed": passed,
        "quality_score": score,
        "minimum_score": int(min_score),
        "issues": issues,
        "face": face,
        "fullbody": fullbody,
        "background": background,
        "single_character": single,
        "image": image,
    }
