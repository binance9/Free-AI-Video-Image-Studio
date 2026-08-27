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
            self._set(job_id, status="running", progress=10, stage="Tối ưu mesh", detail="Blender đang giảm poly…")
            out = self.service.root / "jobs" / job_id
            self._set(job_id, progress=25, stage="Tạo xương + Gắn skin", detail="Blender đang tạo skeleton và bind skin weight…")
            result = self.service.convert(source, out, target_faces=target_faces)
            self._set(job_id, progress=80, stage="Validate", detail="Đang kiểm tra skin/joints/weights/animation thật…")
            validation = result.get("validation") or {}
            animation_ok = bool(validation.get("animation_ok"))
            meta = {
                "source": "game_ready",
                "parent_asset_id": asset_id,
                "game_ready": True,
                "game_ready_pass": bool(validation.get("ok")) and animation_ok,
                "rigged": bool(result.get("rigged", True)),
                "skin_method": result.get("skin_method"),
                "animations": result.get("animations", ["idle", "run", "attack_01"]),
                "faces_before": result.get("faces_before"),
                "faces_after": result.get("faces_after"),
                "bones": result.get("bones"),
                "target_faces": target_faces,
                "validation": validation,
                "suggested_filename": "game_ready.glb",
            }
            payload = self.workspace.create_asset(result["model_path"], None, meta)
            payload.update(meta)
            if not animation_ok:
                missing_or_static = [
                    c for c in ("idle", "run", "attack_01")
                    if not validation.get("required_clips_animated", {}).get(c)
                ]
                self._set(
                    job_id, status="partial_success", progress=100, stage="Game Ready một phần",
                    detail=(
                        "Mesh + skin OK nhưng animation chưa đạt: " + ", ".join(missing_or_static)
                        + " (đứng yên hoặc thiếu) - KHÔNG tính là Game Ready PASS đầy đủ."
                    ),
                    result=payload,
                )
            else:
                self._set(job_id, status="done", progress=100, stage="Game Ready xong",
                           detail="GLB đã có skeleton + skin thật + idle/run/attack_01 có chuyển động thật",
                           result=payload)
        except Exception as exc:
            self._set(job_id, status="error", progress=100, stage="Game Ready lỗi", detail=str(exc), error=str(exc))
