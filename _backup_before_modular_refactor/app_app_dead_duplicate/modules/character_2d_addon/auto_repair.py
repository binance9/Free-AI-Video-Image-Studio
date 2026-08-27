from __future__ import annotations

import io
from pathlib import Path
from PIL import Image

from .prompt_builder import NEGATIVE_PROMPT, build_repair_prompt


def repair_anchor(image_path: str | Path, image_service, profile, output_path: str | Path, issues: list[str], *, fast: bool = False) -> dict:
    src = Path(image_path)
    out = Path(output_path)
    quality = "fast" if fast else "medium"
    strength = 0.22
    if "fullbody" in issues:
        strength = 0.32
    elif "background" in issues:
        strength = 0.26
    data = image_service.edit(
        src,
        build_repair_prompt(profile, issues),
        "illustration",
        "1024x1536",
        quality,
        strength=strength,
        negative_prompt=NEGATIVE_PROMPT,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(data)) as im:
        im.save(out, "PNG")
    return {"path": str(out), "issues": list(issues), "strength": strength, "quality": quality}
