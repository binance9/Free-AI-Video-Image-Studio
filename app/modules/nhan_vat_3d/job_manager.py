"""Background jobs for local 3D generation."""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from pathlib import Path

from app.core.shared_services import JobCancelled, heavy_gpu_job_lock
from app.core.job_log_broker import job_log_broker


class Model3DJobManager:
    def __init__(self, service, workspace, jobs_root: str | Path):
        self.service = service
        self.workspace = workspace
        self.root = Path(jobs_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    def _new(self, kind: str) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=False)
        with self._lock:
            self._cancel_events[job_id] = threading.Event()
            self._jobs[job_id] = {
                "job_id": job_id,
                "kind": kind,
                "status": "queued",
                "progress": 1,
                "stage": "Đang xếp hàng",
                "detail": "",
                "created_at": time.time(),
                "updated_at": time.time(),
                "result": None,
                "error": None,
                "log": [],
                "cancellable": True,
            }
        return job_id, folder

    def _update(self, job_id: str, progress=None, stage=None, detail=None, log=None, **extra):
        with self._lock:
            job = self._jobs[job_id]
            if progress is not None:
                job["progress"] = max(job["progress"], min(100, int(progress)))
            if stage is not None:
                job["stage"] = stage
            if detail is not None:
                job["detail"] = detail
            if log:
                job["log"].append(str(log)[-1200:])
                job["log"] = job["log"][-30:]
                job_log_broker.publish("character_3d", job_id, str(log), "stdout")
            job.update(extra)
            job["updated_at"] = time.time()

    def _progress_cb(self, job_id: str):
        def cb(progress: int, stage: str, detail: str = ""):
            self._update(job_id, progress=progress, stage=stage, detail=detail, log=detail)
        return cb

    def start_image(self, image_path: str | Path, *, prompt="", style="cartoon3d", resolution=256, texture=False, preview=False, backend="quick", optimize_mesh=True, mesh_profile="hd") -> str:
        job_id, folder = self._new("image")
        src = Path(image_path)
        saved = folder / ("input" + (src.suffix.lower() or ".png"))
        shutil.copy2(src, saved)

        def worker():
            self._update(job_id, status="running", progress=3, stage="Chuẩn bị ảnh")
            try:
                with heavy_gpu_job_lock(
                    owner="character_3d", cancel_event=self._cancel_events[job_id],
                    on_wait=lambda _w: self._update(job_id, stage="Đang chờ GPU", detail="Đồ vật 3D đang dùng GPU…"),
                ):
                    input_for_3d=saved
                    if prompt.strip() and self.service.image_service is not None:
                        self._update(job_id,progress=10,stage="Kết hợp ảnh + mô tả",detail="Refine concept trước khi dựng shape")
                        combined=folder/"combined_input.png"
                        combined.write_bytes(self.service.image_service.edit(saved,prompt,style,"1024x1024","high",cancel_event=self._cancel_events[job_id],progress=self._progress_cb(job_id)))
                        input_for_3d=combined
                    result = self.service.from_image(
                        input_for_3d,
                        folder / "out",
                        resolution=resolution,
                        texture=texture,
                        render_preview=preview,
                        progress=self._progress_cb(job_id),
                        backend=backend,
                        optimize_mesh=optimize_mesh,
                        mesh_profile=mesh_profile,
                        cancel_event=self._cancel_events[job_id],
                    )
                payload = self.workspace.create_asset(
                    result["model_path"],
                    result.get("preview_path"),
                    {
                        "source": "image",
                        "prompt": prompt or None,
                        "resolution": int(resolution),
                        "texture": bool(result.get("texture_applied", texture)),
                        "backend": result.get("backend", "triposr"),
                        "device": result.get("device"),
                        "quality_backend": backend,
                        "mesh_optimized": bool(result.get("mesh_optimized", False)),
                        "faces_before": result.get("faces_before"),
                        "faces_after": result.get("faces_after"),
                        "mesh_profile": result.get("mesh_profile", mesh_profile if optimize_mesh else "original"),
                        "normalization": result.get("normalization"),
                        "visual_qa": result.get("visual_qa"), "source_image": result.get("source_image"),
                        "attempt_count": result.get("attempt_count", 1), "retry_count": result.get("retry_count", 0),
                        "selected_candidate": result.get("selected_candidate", 1),
                        "ready_for_rig": bool(result.get("ready_for_rig", False)), "quality_stage": result.get("quality_stage", "DRAFT"),
                    },
                )
                self._update(job_id, status="done", progress=100, stage="Hoàn tất", detail="GLB đã tạo xong", result=payload)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(job_id, status="error", stage="Lỗi", detail=str(exc), error=str(exc), log=str(exc))

        threading.Thread(target=job_log_broker.bound("character_3d",job_id,worker), daemon=True, name=f"aivf3d-{job_id[:8]}").start()
        return job_id

    def start_prompt(self, prompt: str, *, style="cartoon3d", resolution=256, texture=False, preview=False, backend="quick", optimize_mesh=True, mesh_profile="hd") -> str:
        job_id, folder = self._new("prompt")

        def worker():
            self._update(job_id, status="running", progress=3, stage="Chuẩn bị")
            try:
                def cb(progress: int, stage: str, detail: str = ""):
                    mapped = 25 + int(progress * 0.75) if progress >= 1 else progress
                    self._update(job_id, progress=mapped, stage=stage, detail=detail, log=detail)

                self._update(job_id, progress=7, stage="Tạo concept 2D")
                with heavy_gpu_job_lock(
                    owner="character_3d", cancel_event=self._cancel_events[job_id],
                    on_wait=lambda _w: self._update(job_id, stage="Đang chờ GPU", detail="Đồ vật 3D đang dùng GPU…"),
                ):
                    result = self.service.from_prompt(
                        prompt,
                        folder,
                        style=style,
                        resolution=resolution,
                        texture=texture,
                        render_preview=preview,
                        progress=cb,
                        backend=backend,
                        optimize_mesh=optimize_mesh,
                        mesh_profile=mesh_profile,
                        cancel_event=self._cancel_events[job_id],
                    )
                payload = self.workspace.create_asset(
                    result["model_path"],
                    result.get("preview_path"),
                    {
                        "source": "prompt",
                        "prompt": prompt,
                        "style": style,
                        "resolution": int(resolution),
                        "texture": bool(result.get("texture_applied", texture)),
                        "backend": result.get("backend", "triposr"),
                        "device": result.get("device"),
                        "quality_backend": backend,
                        "mesh_optimized": bool(result.get("mesh_optimized", False)),
                        "faces_before": result.get("faces_before"),
                        "faces_after": result.get("faces_after"),
                        "mesh_profile": result.get("mesh_profile", mesh_profile if optimize_mesh else "original"),
                        "normalization": result.get("normalization"),
                        "visual_qa": result.get("visual_qa"), "source_image": result.get("source_image"),
                        "attempt_count": result.get("attempt_count", 1), "retry_count": result.get("retry_count", 0),
                        "selected_candidate": result.get("selected_candidate", 1),
                        "ready_for_rig": bool(result.get("ready_for_rig", False)), "quality_stage": result.get("quality_stage", "DRAFT"),
                    },
                )
                self._update(job_id, status="done", progress=100, stage="Hoàn tất", detail="Concept + GLB đã tạo xong", result=payload)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(job_id, status="error", stage="Lỗi", detail=str(exc), error=str(exc), log=str(exc))

        threading.Thread(target=job_log_broker.bound("character_3d",job_id,worker), daemon=True, name=f"aivf3dp-{job_id[:8]}").start()
        return job_id

    def start_colorize(self, mesh_path: str | Path, image_path: str | Path) -> str:
        job_id, folder = self._new("colorize")
        mesh_src = Path(mesh_path)
        image_src = Path(image_path)
        saved_mesh = folder / "input.glb"
        saved_image = folder / ("reference" + (image_src.suffix.lower() or ".png"))
        shutil.copy2(mesh_src, saved_mesh)
        shutil.copy2(image_src, saved_image)

        def worker():
            self._update(job_id, status="running", progress=3, stage="Chuẩn bị tô màu", detail="Giữ nguyên GLB gốc")
            try:
                with heavy_gpu_job_lock(
                    owner="character_3d", cancel_event=self._cancel_events[job_id],
                    on_wait=lambda _w: self._update(job_id, stage="Đang chờ GPU", detail="Đồ vật 3D đang dùng GPU…"),
                ):
                    result = self.service.colorize_existing(
                        saved_mesh, saved_image, folder / "paint_out", progress=self._progress_cb(job_id),
                        cancel_event=self._cancel_events[job_id]
                    )
                payload = self.workspace.create_asset(
                    result["model_path"], None,
                    {
                        "source": "existing_mesh_paint",
                        "texture": True,
                        "backend": result.get("backend", "character-hd-hunyuan3d-paint"),
                        "device": result.get("device"),
                        "texture_size": result.get("texture_size"),
                        "mesh_profile": "existing",
                    },
                )
                self._update(job_id, status="done", progress=100, stage="Hoàn tất màu HD",
                             detail="GLB màu đã tạo · mesh trắng gốc vẫn được giữ", result=payload)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:
                self._update(job_id, status="error", stage="Lỗi Paint", detail=str(exc), error=str(exc), log=str(exc))

        threading.Thread(target=job_log_broker.bound("character_3d",job_id,worker), daemon=True, name=f"aivf3dpaint-{job_id[:8]}").start()
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancel_events.get(job_id)
            job = self._jobs.get(job_id)
            if not event or not job or job.get("status") not in {"queued", "running", "cancelling"}:
                return False
            event.set()
            job["status"] = "cancelling"
            job["stage"] = "Đang dừng…"
            job["detail"] = "Đang kết thúc tiến trình AI 3D an toàn"
            job["updated_at"] = time.time()
            return True

    def cancel_all(self) -> int:
        with self._lock:
            ids = [jid for jid, job in self._jobs.items() if job.get("status") in {"queued", "running", "cancelling"}]
        return sum(1 for jid in ids if self.cancel(jid))

    def get(self, job_id: str) -> dict:
        clean = "".join(c for c in str(job_id) if c.isalnum())
        if clean != job_id or len(clean) < 8:
            raise ValueError("Mã job không hợp lệ")
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError("Không tìm thấy job 3D")
            job = dict(self._jobs[job_id])
            job["log"] = list(job.get("log") or [])
            return job
