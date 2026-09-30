from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

from .service import VideoGenerationCancelled

try:
    from app.core.job_log_broker import job_log_broker
except Exception:
    job_log_broker = None


class VideoAIJobManager:
    def __init__(self, service, workspace):
        self.service = service
        self.workspace = workspace
        self._jobs = {}
        self._events = {}
        self._lock = threading.RLock()

    def _new(self, kind: str):
        jid = uuid4().hex
        now = time.time()
        with self._lock:
            self._events[jid] = threading.Event()
            self._jobs[jid] = {
                "job_id": jid, "kind": kind, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "detail": "", "created_at": now, "updated_at": now,
                "result": None, "error": None, "cancellable": True,
            }
        return jid

    def _update(self, jid, **changes):
        with self._lock:
            if jid in self._jobs:
                self._jobs[jid].update(changes)
                self._jobs[jid]["updated_at"] = time.time()

    def _progress(self, jid):
        def cb(pct, stage, detail=""):
            self._update(jid, status="running", progress=max(1, min(99, int(pct))), stage=stage, detail=detail)
        return cb

    def _run(self, jid, fn):
        def worker():
            try:
                self._update(jid, status="running", progress=3, stage="Chuẩn bị GPU")
                result = fn()
                self._update(jid, status="done", progress=100, stage="Hoàn tất", detail="MP4 đã sẵn sàng", result=result, cancellable=False)
            except VideoGenerationCancelled as exc:
                self._update(jid, status="cancelled", stage="Đã dừng", detail=str(exc), cancellable=False)
            except Exception as exc:
                self._update(jid, status="error", stage="Lỗi AI video", detail=str(exc), error=str(exc), cancellable=False)
        target = worker
        if job_log_broker is not None:
            try:
                target = job_log_broker.bound("video_ai", jid, worker)
            except Exception:
                pass
        threading.Thread(target=target, daemon=True, name=f"aivf-video-ai-{jid[:8]}").start()

    def start_text(self, **kwargs):
        jid = self._new("text_to_video")
        self._run(jid, lambda: self.service.generate_text(cancel_event=self._events[jid], progress=self._progress(jid), **kwargs))
        return jid

    def start_image(self, image_path, **kwargs):
        jid = self._new("image_to_video")
        src = Path(image_path)
        staged = self.workspace.root / f"_input_{jid}{src.suffix.lower() or '.png'}"
        shutil.copy2(src, staged)
        def fn():
            try:
                return self.service.generate_image(staged, cancel_event=self._events[jid], progress=self._progress(jid), **kwargs)
            finally:
                staged.unlink(missing_ok=True)
        self._run(jid, fn)
        return jid

    def get(self, jid):
        with self._lock:
            if jid not in self._jobs:
                raise KeyError(jid)
            return dict(self._jobs[jid])

    def cancel(self, jid):
        with self._lock:
            event = self._events.get(jid)
            job = self._jobs.get(jid)
            if not event or not job or job.get("status") in {"done", "error", "cancelled"}:
                return False
            event.set()
            self._update(jid, stage="Đang dừng", detail="Sẽ dừng ở diffusion step an toàn gần nhất")
            return True
