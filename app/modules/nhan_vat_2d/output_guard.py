from __future__ import annotations

from pathlib import Path
import shutil

import numpy as np
from PIL import Image


LIGHT_BG_RGBA = (235, 235, 235, 255)


def inspect_image(image_path: str | Path) -> dict:
    path = Path(image_path)
    if not path.is_file():
        return {"ok": False, "reason": "file_missing", "image_path": str(path)}

    try:
        with Image.open(path).convert("RGBA") as im:
            arr = np.array(im)
    except Exception as exc:
        return {"ok": False, "reason": f"inspect_error:{exc}", "image_path": str(path)}

    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3].astype(np.float32)
    total_pixels = float(alpha.shape[0] * alpha.shape[1]) or 1.0

    visible_mask = alpha > 8
    visible_pixels = int(visible_mask.sum())
    visible_ratio = visible_pixels / total_pixels

    if visible_pixels == 0:
        return {
            "ok": False,
            "reason": "fully_transparent",
            "image_path": str(path),
            "visible_ratio": round(visible_ratio, 4),
            "brightness": 0.0,
            "contrast": 0.0,
            "non_black_ratio": 0.0,
            "unique_colors": 0,
            "blank": True,
        }

    vis_rgb = rgb[visible_mask]
    brightness = float(vis_rgb.mean())
    contrast = float(vis_rgb.std())
    non_black_ratio = float(((vis_rgb > 12).any(axis=1)).mean()) if len(vis_rgb) else 0.0

    sample_step = max(1, len(vis_rgb) // 50000)
    sample = vis_rgb[::sample_step].astype(np.uint8)
    unique_colors = int(len(np.unique(sample, axis=0))) if len(sample) else 0

    h, w = rgb.shape[:2]
    band = max(4, min(h, w) // 16)
    edge_pixels = np.concatenate([
        rgb[:band, :, :].reshape(-1, 3),
        rgb[-band:, :, :].reshape(-1, 3),
        rgb[:, :band, :].reshape(-1, 3),
        rgb[:, -band:, :].reshape(-1, 3),
    ], axis=0)
    edge_brightness = float(edge_pixels.mean()) if len(edge_pixels) else 0.0
    dark_edge_ratio = float((edge_pixels.mean(axis=1) < 28).mean()) if len(edge_pixels) else 1.0

    issues: list[str] = []
    if visible_ratio < 0.02:
        issues.append("too_little_visible_content")
    if brightness < 10:
        issues.append("too_dark")
    if contrast < 6:
        issues.append("too_flat")
    if non_black_ratio < 0.03:
        issues.append("mostly_black")
    if unique_colors < 4 and contrast < 12:
        issues.append("too_few_colors")
    # Relaxed: edge_brightness 45->28, dark_edge_ratio 0.55->0.75.  Many good
    # 2D renders with light gray backgrounds measured edge_brightness 30-45
    # (slightly darker edges from character shadow) and were wrongly rejected.
    if edge_brightness < 28 or dark_edge_ratio > 0.75:
        issues.append("dark_background_edges")

    return {
        "ok": len(issues) == 0,
        "reason": "ok" if not issues else ",".join(issues),
        "image_path": str(path),
        "visible_ratio": round(visible_ratio, 4),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "non_black_ratio": round(non_black_ratio, 4),
        "unique_colors": unique_colors,
        "edge_brightness": round(edge_brightness, 2),
        "dark_edge_ratio": round(dark_edge_ratio, 4),
        "blank": bool(issues),
        "issues": issues,
    }


def flatten_preview(src_path: str | Path, dst_path: str | Path, bg: tuple[int, int, int, int] = LIGHT_BG_RGBA) -> str:
    src = Path(src_path)
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src).convert("RGBA") as im:
        bg_im = Image.new("RGBA", im.size, bg)
        merged = Image.alpha_composite(bg_im, im).convert("RGB")
        merged.save(dst, format="PNG")
    return str(dst)


def save_export_image(src_path: str | Path, dst_path: str | Path, *, flatten: bool = True) -> str:
    src = Path(src_path)
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if flatten:
        return flatten_preview(src, dst)
    shutil.copy2(src, dst)
    return str(dst)


def build_repair_prompt(base_prompt: str) -> str:
    return (
        f"{base_prompt}. Single character only, clearly visible, centered, compact game-ready framing, "
        "full body visible, clean silhouette, bright studio lighting, light gray plain background, "
        "sharp character details, no empty frame, no black frame, no blank image"
    )


def build_repair_negative_prompt(base_negative: str = "") -> str:
    extra = (
        "black image, blank image, empty image, dark frame, black frame, silhouette only, "
        "underexposed, fully transparent image, cropped body, missing character, multiple characters, messy background"
    )
    if base_negative and base_negative.strip():
        return f"{base_negative}, {extra}"
    return extra
