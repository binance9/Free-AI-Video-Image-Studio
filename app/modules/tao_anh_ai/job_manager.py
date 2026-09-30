from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

from app.core.shared_services import JobCancelled
from app.core.job_log_broker import job_log_broker
from .service import generation_mode


class AiImageJobManager:
    def __init__(self, service, workspace):
        self.service = service
        self.workspace = workspace
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, threading.Event] = {}

    def _new(self, kind: str, *, mode: str) -> str:
        jid = uuid4().hex
        now = time.time()
        with self._lock:
            self._events[jid] = threading.Event()
            self._jobs[jid] = {
                "job_id": jid, "kind": kind, "mode": mode, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "detail": "", "message": "Đang chờ engine ảnh local",
                "preview_type": "image", "preview_url": None, "preview_path": None, "created_at": now,
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
            self._update(jid, status="running", progress=int(pct), stage=stage, detail=detail, message=detail)
        return cb

    def start_generate(self, *, prompt: str, style: str, size: str, quality: str, backend: str = "auto") -> str:
        jid = self._new("generate", mode="TEXT2IMG")
        def worker():
            try:
                print(f"AIVF_IMAGE_JOB|{jid}|mode=TEXT2IMG|input_image_used=false", flush=True)
                self._update(jid, status="running", progress=5, stage="TEXT2IMG", detail="No input image; text-to-image pipeline", message="TEXT2IMG | input_image_used=false")
                data = self.service.generate(
                    prompt, style, size, quality, backend=backend,
                    cancel_event=self._events[jid], progress=self._progress(jid),
                )
                if self._events[jid].is_set():
                    raise JobCancelled("Đã dừng tạo ảnh")
                metadata = self.service.consume_metadata() if hasattr(self.service, "consume_metadata") else {}
                result = self.workspace.save(data)
                metadata["output_path"] = str(self.workspace.path(result["image_id"]))
                result["metadata"] = metadata
                self._update(jid, status="done", progress=100, stage="Hoàn tất", detail="Ảnh đã tạo xong", message="Draft → refine → final", preview_url=result["url"], result=result)
            except JobCancelled as exc:
                self._update(jid, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(jid, status="error", stage="Lỗi AI ảnh", detail=str(exc), error=str(exc))
        threading.Thread(target=job_log_broker.bound("image",jid,worker), daemon=True, name=f"aivf-img-{jid[:8]}").start()
        return jid

    def start_edit(self, image_path: str | Path, *, prompt: str, style: str, size: str, quality: str, mask_path: str | Path | None = None) -> str:
        mode = generation_mode(has_image=True, prompt=prompt, has_mask=mask_path is not None)
        pipeline_mode = "INPAINT" if mask_path else "PRESERVE_IMG2IMG"
        jid = self._new("edit", mode=mode)
        src = Path(image_path)
        saved = self.workspace.root / f"_edit_{jid}{src.suffix.lower() or '.png'}"
        shutil.copy2(src, saved)
        saved_mask = None
        if mask_path:
            mask_src = Path(mask_path)
            saved_mask = self.workspace.root / f"_mask_{jid}{mask_src.suffix.lower() or '.png'}"
            shutil.copy2(mask_src, saved_mask)
        self._update(jid, preview_path=str(saved), preview_url=f"/api/ai-image/jobs/{jid}/preview", pipeline_mode=pipeline_mode, input_image_used=True, message=f"{mode} | {pipeline_mode} | input_image_used=true")
        def worker():
            try:
                print(f"AIVF_IMAGE_JOB|{jid}|mode={mode}|input_image_used=true|pipeline={pipeline_mode}", flush=True)
                self._update(jid, status="running", progress=5, stage=mode, detail=f"Input image loaded: {saved.name}", message=f"{mode} | {pipeline_mode} | input_image_used=true")
                data = self.service.edit(saved, prompt, style, size, quality, mask_path=saved_mask, mode=mode, cancel_event=self._events[jid], progress=self._progress(jid))
                if self._events[jid].is_set():
                    raise JobCancelled("Đã dừng sửa ảnh")
                metadata = self.service.consume_metadata() if hasattr(self.service, "consume_metadata") else {}
                result = self.workspace.save(data)
                metadata["output_path"] = str(self.workspace.path(result["image_id"]))
                result["metadata"] = metadata
                self._update(jid, status="done", progress=100, stage="Hoàn tất", detail="Ảnh đã sửa xong", message="Refine → final", preview_url=result["url"], result=result)
            except JobCancelled as exc:
                self._update(jid, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(jid, status="error", stage="Lỗi AI ảnh", detail=str(exc), error=str(exc))
            finally:
                saved.unlink(missing_ok=True)
                if saved_mask:
                    saved_mask.unlink(missing_ok=True)
        threading.Thread(target=job_log_broker.bound("image",jid,worker), daemon=True, name=f"aivf-imgedit-{jid[:8]}").start()
        return jid

    def get(self, jid: str) -> dict:
        with self._lock:
            if jid not in self._jobs:
                raise KeyError(jid)
            return dict(self._jobs[jid])

    def preview_path(self, jid: str) -> Path:
        with self._lock:
            job = self._jobs.get(jid)
            if not job or not job.get("preview_path"):
                raise KeyError(jid)
            path = Path(job["preview_path"]).resolve()
        if not path.is_file() or self.workspace.root.resolve() not in path.parents:
            raise KeyError(jid)
        return path

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
