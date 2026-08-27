from __future__ import annotations
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def structural_reference_similarity(candidate_path: str | Path, reference_path: str | Path) -> dict:
    """Color-insensitive fallback identity score for reference edits.

    Compares resized luminance and edges, so recoloring does not collapse identity to 0.
    This is intentionally lightweight and dependency-free.
    """
    try:
        def prep(path):
            with Image.open(path) as im:
                gray = im.convert("L").resize((128, 128), Image.Resampling.LANCZOS)
                edge = gray.filter(ImageFilter.FIND_EDGES)
                g = np.asarray(gray, dtype=np.float32) / 255.0
                e = np.asarray(edge, dtype=np.float32) / 255.0
            # center each channel so light-background differences matter less
            g = g - float(g.mean())
            e = e - float(e.mean())
            return g, e

        ga, ea = prep(candidate_path)
        gb, eb = prep(reference_path)

        def cosine(a, b):
            av = a.reshape(-1)
            bv = b.reshape(-1)
            den = float(np.linalg.norm(av) * np.linalg.norm(bv))
            if den <= 1e-8:
                return 0.0
            return float(np.dot(av, bv) / den)

        lum = max(0.0, min(1.0, (cosine(ga, gb) + 1.0) / 2.0))
        edge = max(0.0, min(1.0, (cosine(ea, eb) + 1.0) / 2.0))
        score = edge * 0.68 + lum * 0.32
        return {
            "ok": score >= 0.58,
            "similarity": round(score, 4),
            "threshold": 0.58,
            "method": "grayscale_edge_fallback",
            "edge_similarity": round(edge, 4),
            "luminance_similarity": round(lum, 4),
        }
    except Exception as exc:
        return {"ok": None, "similarity": None, "threshold": 0.58, "method": "grayscale_edge_fallback", "error": str(exc)}


def clip_reference_similarity(attribute_lock, candidate_path: str | Path, reference_path: str | Path, threshold: float = 0.74) -> dict:
    """Compare candidate vs reference using CLIP vision with a deterministic fallback."""
    try:
        import torch
        attribute_lock._load()
        processor = attribute_lock._processor
        model = attribute_lock._model
        device = attribute_lock._device
        with Image.open(candidate_path) as a, Image.open(reference_path) as b:
            images = [a.convert("RGB"), b.convert("RGB")]
            inputs = processor(images=images, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device)
        with torch.inference_mode():
            feats = model.get_image_features(pixel_values=pixel_values)
            feats = feats / feats.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            sim = float((feats[0] * feats[1]).sum().detach().cpu())
        threshold = float(threshold)
        return {"ok": sim >= threshold, "similarity": round(sim, 4), "threshold": round(threshold, 4), "method": "clip"}
    except Exception as exc:
        fallback = structural_reference_similarity(candidate_path, reference_path)
        fallback["clip_error"] = str(exc)
        return fallback
