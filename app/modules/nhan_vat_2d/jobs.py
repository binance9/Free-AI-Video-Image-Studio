from __future__ import annotations

import threading
import time
import uuid
from app.core.job_log_broker import job_log_broker


class Character2DJobs:
    def __init__(self):
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}

    def start(self, worker) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "message": "Chuẩn bị Character 2D",
                "detail": "", "preview_type": "image", "preview_url": None,
                "result": None, "error": None, "updated_at": time.time(),
            }
        def run():
            try:
                self.update(job_id, status="running", progress=8, stage="Phân tích đầu vào", message="Ảnh nguồn + mô tả")
                result = worker(lambda p,s,m="": self.update(job_id,status="running",progress=p,stage=s,message=m,detail=m))
                preview = result.get("image_url") or result.get("best_rejected_url")
                self.update(job_id,status="done",progress=100,stage="Hoàn tất",message="Ảnh Character 2D final",preview_url=preview,result=result)
            except Exception as exc:
                self.update(job_id,status="error",stage="Lỗi Character 2D",message=str(exc),detail=str(exc),error=str(exc))
        threading.Thread(target=job_log_broker.bound("character_2d",job_id,run),daemon=True,name=f"aivf-char2d-{job_id[:8]}").start()
        return job_id

    def update(self, job_id: str, **values):
        with self._lock:
            self._jobs[job_id].update(values,updated_at=time.time())

    def get(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs: raise KeyError(job_id)
            return dict(self._jobs[job_id])
