from __future__ import annotations

import io
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw

from .prompt_builder import NEGATIVE_PROMPT, build_face_refine_prompt


def _fallback_head_box(size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    # Narrow upper-center box: never include chest/large shoulder areas.
    return (int(w * 0.33), int(h * 0.015), int(w * 0.67), int(h * 0.255))


def _detect_face_box(image_path: Path, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    try:
        import cv2
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))
        if len(faces) == 0:
            return None
        w_img, h_img = size
        # Prefer a face in the upper half and near center.
        candidates = []
        for x, y, w, h in faces:
            cx = x + w / 2
            cy = y + h / 2
            if cy > h_img * 0.55:
                continue
            center_penalty = abs(cx - w_img / 2) / max(1, w_img)
            candidates.append((w * h - center_penalty * 1000, x, y, w, h))
        if not candidates:
            return None
        _score, x, y, w, h = max(candidates)
        # Expand enough for brows/jaw/hairline, but avoid shoulders/chest.
        ex = int(w * 0.28)
        ey_top = int(h * 0.35)
        ey_bottom = int(h * 0.30)
        x1 = max(0, x - ex)
        y1 = max(0, y - ey_top)
        x2 = min(w_img, x + w + ex)
        y2 = min(h_img, y + h + ey_bottom)
        return (x1, y1, x2, y2)
    except Exception:
        return None


def _soft_oval_mask(size: tuple[int, int]) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    pad_x = max(2, int(w * 0.08))
    pad_y = max(2, int(h * 0.05))
    draw.ellipse((pad_x, pad_y, w - pad_x, h - pad_y), fill=215)
    return mask.filter(ImageFilter.GaussianBlur(radius=max(5, min(w, h) // 22)))


def refine_face(image_path: str | Path, image_service, profile, output_path: str | Path) -> dict:
    src_path = Path(image_path)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as source:
        base = source.convert("RGB")
        detected = _detect_face_box(src_path, base.size)
        box = detected or _fallback_head_box(base.size)
        face = base.crop(box)
        face_path = out_path.parent / "_face_input.png"
        face.resize((512, 512), Image.Resampling.LANCZOS).save(face_path)

    refined_bytes = image_service.edit(
        face_path,
        build_face_refine_prompt(profile),
        "illustration",
        "512x512",
        "medium",
        strength=0.24,
        negative_prompt=NEGATIVE_PROMPT,
    )
    with Image.open(io.BytesIO(refined_bytes)) as refined_raw, Image.open(src_path) as source:
        base = source.convert("RGB")
        refined = refined_raw.convert("RGB").resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
        mask = _soft_oval_mask(refined.size)
        base.paste(refined, (box[0], box[1]), mask)
        base.save(out_path, format="PNG")

    face_path.unlink(missing_ok=True)
    return {"path": str(out_path), "box": list(box), "detected": bool(detected), "strength": 0.24}
