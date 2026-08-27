"""Report local/free AI dependency availability without importing heavy models."""
from __future__ import annotations

import importlib.util
from pathlib import Path


_REQUIRED = {
    "faster_whisper": "Phụ đề local",
    "argostranslate": "Dịch local",
    "torch": "AI ảnh local",
    "diffusers": "AI ảnh local",
    "transformers": "AI ảnh local",
}


def dependency_status(model_dir: str | Path) -> dict:
    packages = {name: bool(importlib.util.find_spec(name)) for name in _REQUIRED}
    return {
        "free_local": True,
        "paid_api_required": False,
        "packages": packages,
        "ready": all(packages.values()),
        "model_dir": str(Path(model_dir).resolve()),
        "note": "Model được tải miễn phí ở lần dùng đầu và lưu local trên máy.",
    }
