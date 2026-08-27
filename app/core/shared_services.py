"""Cross-cutting infra used by many feature modules - not a "chức năng"
(feature) module itself, so it lives in app/core instead of app/modules.

- JobCancelled / terminate_process: cooperative cancel for any long-running
  local subprocess job (used by nhan_vat_3d, lam_sach_video, tai_video,
  tao_anh_ai job managers).
- dependency_status: reports whether free/local AI packages (whisper,
  argos, torch, diffusers, transformers) are installed, without importing
  heavy models - used by the settings UI.
- heavy_gpu_job_lock: lightweight shared lock so at most one heavy local 3D
  generation job runs at a time (RTX 3050-class VRAM budget). Added for
  do_vat_3d (Phase 1.6). nhan_vat_3d's own job manager is NOT wired to this
  lock yet - deliberately not touched, see do_vat_3d/README_MODULE.md
  "Known limitations" for why.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


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


_heavy_gpu_lock = threading.Lock()


def heavy_gpu_job_is_busy() -> bool:
    return _heavy_gpu_lock.locked()


@contextmanager
def heavy_gpu_job_lock(*, on_wait=None) -> Iterator[None]:
    """Block until it's this job's turn to use the shared heavy-3D-GPU slot.

    on_wait(bool) is called once with True right before blocking if the lock
    is already held by another job, so callers can update job status to
    "Đang chờ GPU" before the (potentially long) wait.
    """
    if _heavy_gpu_lock.locked() and on_wait:
        on_wait(True)
    _heavy_gpu_lock.acquire()
    try:
        yield
    finally:
        _heavy_gpu_lock.release()
