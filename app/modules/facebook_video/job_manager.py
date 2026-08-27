"""Background jobs for Facebook video imports."""

from __future__ import annotations

import shutil
import inspect
import threading
import time
from pathlib import Path
from uuid import uuid4

from .downloader import FacebookVideoDownloader
from app.modules.job_control import JobCancelled


class FacebookVideoJobManager:
    def __init__(self, downloader: FacebookVideoDownloader, workspace, jobs_dir: str | Path):
        self.downloader = downloader
        self.workspace = workspace
        self.jobs_dir = Path(jobs_dir).resolve()
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}

    def start(self, url: str) -> dict:
        safe_url = self.downloader.validate_url(url)
        job_id = uuid4().hex
        now = time.time()
        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "Xếp hàng tải Facebook",
            "detail": "Chuẩn bị…",
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._cancel_events[job_id] = threading.Event()
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job_id, safe_url), daemon=True)
        thread.start()
        return dict(job)

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            return dict(job)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job=self._jobs.get(job_id)
            event=self._cancel_events.get(job_id)
            if not job or not event or job.get("status") not in {"queued","running","cancelling"}:
                return False
            event.set()
            job.update(status="cancelling", stage="Đang dừng…", detail="Đang kết thúc tải Facebook", updated_at=time.time())
            return True

    def cancel_all(self) -> int:
        with self._lock:
            ids=[jid for jid,j in self._jobs.items() if j.get("status") in {"queued","running","cancelling"}]
        return sum(1 for jid in ids if self.cancel(jid))

    def file_path(self, job_id: str) -> Path:
        job = self.get(job_id)
        result = job.get("result") or {}
        path = Path(result.get("library_path") or "")
        if job.get("status") != "done" or not path.is_file():
            raise FileNotFoundError(job_id)
        return path

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id].update(changes)
            self._jobs[job_id]["updated_at"] = time.time()

    def _progress(self, job_id: str, pct: int, stage: str, detail: str) -> None:
        self._update(job_id, status="running", progress=pct, stage=stage, detail=detail)

    def _run(self, job_id: str, url: str) -> None:
        job_dir = self.jobs_dir / job_id
        try:
            self._update(job_id, status="running", progress=2, stage="Chuẩn bị tải Facebook", detail="Đang mở link công khai…")
            download_kwargs = {}
            try:
                if "cancel_event" in inspect.signature(self.downloader.download).parameters:
                    download_kwargs["cancel_event"] = self._cancel_events[job_id]
            except Exception:
                pass
            downloaded = self.downloader.download(
                url,
                job_dir,
                lambda pct, stage, detail: self._progress(job_id, pct, stage, detail),
                **download_kwargs,
            )
            library_path = Path(downloaded["path"])
            incoming = self.workspace.root / "_facebook_incoming"
            incoming.mkdir(parents=True, exist_ok=True)
            temp = incoming / f"{job_id}{library_path.suffix.lower()}"
            shutil.copy2(library_path, temp)
            original_name = f"{downloaded['title']}{library_path.suffix.lower()}"
            editor = self.workspace.create(temp, original_name)
            result = {
                "editor": editor,
                "title": downloaded["title"],
                "uploader": downloaded["uploader"],
                "video_id": downloaded["video_id"],
                "size_bytes": downloaded["size_bytes"],
                "library_path": str(library_path),
                "download_url": f"/api/facebook-video/jobs/{job_id}/file",
            }
            self._update(
                job_id,
                status="done",
                progress=100,
                stage="Hoàn tất",
                detail="Video Facebook đã được đưa thẳng vào editor",
                result=result,
                error=None,
            )
        except JobCancelled as exc:
            self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
        except Exception as exc:
            self._update(
                job_id,
                status="error",
                stage="Lỗi tải Facebook",
                detail=str(exc),
                error=str(exc),
            )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
