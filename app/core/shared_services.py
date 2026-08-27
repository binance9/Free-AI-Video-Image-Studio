"""Cross-cutting infra used by many feature modules - not a "chức năng"
(feature) module itself, so it lives in app/core instead of app/modules.

- JobCancelled / terminate_process: cooperative cancel for any long-running
  local subprocess job (used by nhan_vat_3d, lam_sach_video, tai_video,
  tao_anh_ai job managers).
- dependency_status: reports whether free/local AI packages (whisper,
  argos, torch, diffusers, transformers) are installed, without importing
  heavy models - used by the settings UI.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any


class JobCancelled(RuntimeError):
    """Raised when a user explicitly cancels a long-running local job."""


def terminate_process(proc: Any) -> None:
    """Terminate only the process tree spawned for one AI Video Factory job."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


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
