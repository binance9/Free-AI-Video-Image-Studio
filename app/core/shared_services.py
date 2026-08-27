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
  do_vat_3d (Phase 1.6); nhan_vat_3d's job manager was wired to the same
  lock in Phase 1.6.1 (see nhan_vat_3d/job_manager.py) so Character 3D and
  Do Vat 3D no longer fight over GPU when run at the same time.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import threading
import time
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
_heavy_gpu_meta_lock = threading.Lock()
_heavy_gpu_owner: str | None = None
_heavy_gpu_owner_since: float | None = None
_heavy_gpu_queue: list[object] = []


def heavy_gpu_job_is_busy() -> bool:
    return _heavy_gpu_lock.locked()


def heavy_gpu_job_status() -> dict:
    """Snapshot of the shared heavy-3D-GPU slot for status/UI display."""
    with _heavy_gpu_meta_lock:
        owner = _heavy_gpu_owner
        since = _heavy_gpu_owner_since
        queued = len(_heavy_gpu_queue)
    return {
        "busy": owner is not None,
        "current_owner": owner,
        "queued_jobs": queued,
        "wait_seconds": round(time.monotonic() - since, 1) if since is not None else 0.0,
    }


@contextmanager
def heavy_gpu_job_lock(*, owner: str = "job", on_wait=None, cancel_event=None, poll_seconds: float = 0.25) -> Iterator[None]:
    """Block until it's this job's turn to use the shared heavy-3D-GPU slot.

    on_wait(bool) is called once with True right before blocking if the lock
    is already held by another job, so callers can update job status to
    "Đang chờ GPU" before the (potentially long) wait.

    cancel_event, if given, is polled while waiting in the queue so a user
    can cancel a still-queued job without waiting for the GPU to free up
    (JobCancelled is raised instead of acquiring the lock).
    """
    global _heavy_gpu_owner, _heavy_gpu_owner_since
    token = object()
    with _heavy_gpu_meta_lock:
        _heavy_gpu_queue.append(token)
        already_busy = _heavy_gpu_lock.locked()
    if already_busy and on_wait:
        on_wait(True)
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled("Đã huỷ trong lúc chờ GPU")
            if _heavy_gpu_lock.acquire(timeout=poll_seconds):
                break
    finally:
        with _heavy_gpu_meta_lock:
            if token in _heavy_gpu_queue:
                _heavy_gpu_queue.remove(token)
    with _heavy_gpu_meta_lock:
        _heavy_gpu_owner = owner
        _heavy_gpu_owner_since = time.monotonic()
    try:
        yield
    finally:
        with _heavy_gpu_meta_lock:
            _heavy_gpu_owner = None
            _heavy_gpu_owner_since = None
        _heavy_gpu_lock.release()
