from __future__ import annotations
from pathlib import Path
from PIL import Image
import numpy as np


def inspect_compact_composition(image_path: str | Path) -> dict:
    """Estimate foreground occupancy against a plain background.

    The compact_game preset wants a readable full-body character with generous
    empty margin instead of a tall concept-art figure filling the whole canvas.
    """
    with Image.open(image_path) as im:
        rgb = np.asarray(im.convert("RGB").resize((256, 256)), dtype=np.float32)
    corners = np.concatenate([
        rgb[:24,:24].reshape(-1,3), rgb[:24,-24:].reshape(-1,3),
        rgb[-24:,:24].reshape(-1,3), rgb[-24:,-24:].reshape(-1,3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(rgb - bg[None,None,:], axis=2)
    mask = dist > 34.0
    # suppress sparse noise
    ys, xs = np.where(mask)
    if len(xs) < 250:
        return {"ok": False, "reason": "foreground_not_detected", "height_ratio": 0.0, "width_ratio": 0.0}
    x0,x1,y0,y1 = int(xs.min()),int(xs.max()),int(ys.min()),int(ys.max())
    hr=(y1-y0+1)/256.0; wr=(x1-x0+1)/256.0
    left=x0/256.0; right=(255-x1)/256.0; top=y0/256.0; bottom=(255-y1)/256.0
    cx=((x0+x1)/2)/255.0
    # generous margins but enough size for readable gear/face
    ok = (0.52 <= hr <= 0.82 and 0.20 <= wr <= 0.72 and left >= 0.08 and right >= 0.08 and top >= 0.06 and bottom >= 0.04 and 0.38 <= cx <= 0.62)
    return {
        "ok": bool(ok), "height_ratio": round(hr,3), "width_ratio": round(wr,3),
        "left_margin": round(left,3), "right_margin": round(right,3),
        "top_margin": round(top,3), "bottom_margin": round(bottom,3),
        "center_x": round(cx,3),
    }
