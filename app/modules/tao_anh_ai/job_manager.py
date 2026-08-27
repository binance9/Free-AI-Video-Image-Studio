from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

from app.core.shared_services import JobCancelled


class AiImageJobManager:
    def __init__(self, service, workspace):
        self.service = service
        self.workspace = workspace
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, threading.Event] = {}

    def _new(self, kind: str) -> str:
        jid = uuid4().hex
        now = time.time()
        with self._lock:
            self._events[jid] = threading.Event()
            self._jobs[jid] = {
                "job_id": jid, "kind": kind, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "detail": "", "created_at": now,
                "updated_at": now, "result": None, "error": None, "cancellable": True,
            }
        return jid

    def _update(self, jid: str, **changes):
        with self._lock:
            if jid not in self._jobs:
                return
            self._jobs[jid].update(changes)
            self._jobs[jid]["updated_at"] = time.time()

    def _progress(self, jid: str):
        def cb(pct: int, stage: str, detail: str = ""):
            self._update(jid, status="running", progress=int(pct), stage=stage, detail=detail)
        return cb

    def start_generate(self, *, prompt: str, style: str, size: str, quality: str) -> str:
        jid = self._new("generate")
        def worker():
            try:
                self._update(jid, status="running", progress=5, stage="Nạp AI ảnh", detail="Model local / cache hiện có")
                data = self.service.generate(prompt, style, size, quality, cancel_event=self._events[jid], progress=self._progress(jid))
                if self._events[jid].is_set():
                    raise JobCancelled("Đã dừng tạo ảnh")
                result = self.workspace.save(data)
                self._update(jid, status="done", progress=100, stage="Hoàn tất", detail="Ảnh đã tạo xong", result=result)
            except JobCancelled as exc:
                self._update(jid, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(jid, status="error", stage="Lỗi AI ảnh", detail=str(exc), error=str(exc))
        threading.Thread(target=worker, daemon=True, name=f"aivf-img-{jid[:8]}").start()
        return jid

    def start_edit(self, image_path: str | Path, *, prompt: str, style: str, size: str, quality: str) -> str:
        jid = self._new("edit")
        src = Path(image_path)
        saved = self.workspace.root / f"_edit_{jid}{src.suffix.lower() or '.png'}"
        shutil.copy2(src, saved)
        def worker():
            try:
                self._update(jid, status="running", progress=5, stage="Nạp AI sửa ảnh", detail="Đang chuẩn bị ảnh tham chiếu")
                data = self.service.edit(saved, prompt, style, size, quality, cancel_event=self._events[jid], progress=self._progress(jid))
                if self._events[jid].is_set():
                    raise JobCancelled("Đã dừng sửa ảnh")
                result = self.workspace.save(data)
                self._update(jid, status="done", progress=100, stage="Hoàn tất", detail="Ảnh đã sửa xong", result=result)
            except JobCancelled as exc:
                self._update(jid, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(jid, status="error", stage="Lỗi AI ảnh", detail=str(exc), error=str(exc))
            finally:
                saved.unlink(missing_ok=True)
        threading.Thread(target=worker, daemon=True, name=f"aivf-imgedit-{jid[:8]}").start()
        return jid

    def get(self, jid: str) -> dict:
        with self._lock:
            if jid not in self._jobs:
                raise KeyError(jid)
            return dict(self._jobs[jid])

    def cancel(self, jid: str) -> bool:
        with self._lock:
            job = self._jobs.get(jid); event = self._events.get(jid)
            if not job or not event or job.get("status") not in {"queued", "running", "cancelling"}:
                return False
            event.set()
            job.update(status="cancelling", stage="Đang dừng…", detail="AI ảnh sẽ dừng ở bước an toàn gần nhất", updated_at=time.time())
            return True

    def cancel_all(self) -> int:
        with self._lock:
            ids = [jid for jid,j in self._jobs.items() if j.get("status") in {"queued","running","cancelling"}]
        return sum(1 for jid in ids if self.cancel(jid))
