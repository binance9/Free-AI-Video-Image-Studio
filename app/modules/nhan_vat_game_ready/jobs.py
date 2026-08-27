from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path


class GameReadyJobManager:
    def __init__(self, service, workspace):
        self.service = service
        self.workspace = workspace
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, asset_id: str, target_faces: int = 45000) -> str:
        source = self.workspace.model_path(asset_id)
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"job_id": job_id, "status": "queued", "progress": 2, "stage": "Xếp hàng", "detail": "Chuẩn bị Game Ready…", "created": time.time()}
        t = threading.Thread(target=self._run, args=(job_id, source, asset_id, target_faces), daemon=True)
        t.start()
        return job_id

    def get(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError("Không tìm thấy Game Ready job")
            return dict(self._jobs[job_id])

    def _set(self, job_id: str, **values):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(values)

    def _run(self, job_id: str, source: Path, asset_id: str, target_faces: int):
        try:
            self._set(job_id, status="running", progress=10, stage="Optimize + Rig", detail="Blender đang giảm poly, tạo xương và skin weight…")
            out = self.service.root / "jobs" / job_id
            result = self.service.convert(source, out, target_faces=target_faces)
            self._set(job_id, progress=90, stage="Export GLB", detail="Đang đóng gói skeleton + animation…")
            meta = {
                "source": "game_ready",
                "parent_asset_id": asset_id,
                "game_ready": True,
                "rigged": bool(result.get("rigged", True)),
                "animations": result.get("animations", ["idle", "run", "attack_01"]),
                "faces_before": result.get("faces_before"),
                "faces_after": result.get("faces_after"),
                "bones": result.get("bones"),
                "target_faces": target_faces,
            }
            payload = self.workspace.create_asset(result["model_path"], None, meta)
            payload.update(meta)
            self._set(job_id, status="done", progress=100, stage="Game Ready xong", detail="GLB đã có skeleton + animation starter", result=payload)
        except Exception as exc:
            self._set(job_id, status="error", progress=100, stage="Game Ready lỗi", detail=str(exc), error=str(exc))
