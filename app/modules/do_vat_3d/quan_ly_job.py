"""Job nen cho do_vat_3d: chay DoVat3DService.tao_do_vat trong thread rieng,
theo doi progress/cancel, luu asset qua Model3DWorkspace (tai dung nguyen -
class nay khong co logic rieng cho nhan vat) roi ghi them asset.json theo
contract GameAsset3D.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from app.core.shared_services import JobCancelled

from .hop_dong_asset import game_asset_from_metadata
from .phan_loai_do_vat import sanitize_ten_asset


class DoVat3DJobManager:
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
                "job_id": job_id, "kind": kind, "status": "queued", "progress": 1,
                "stage": "Đang xếp hàng", "detail": "", "created_at": time.time(),
                "updated_at": time.time(), "result": None, "error": None, "log": [],
                "cancellable": True,
            }
        return job_id, folder

    def _update(self, job_id: str, *, progress=None, stage=None, detail=None, log=None, **extra):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if progress is not None:
                job["progress"] = max(job["progress"], min(100, int(progress)))
            if stage is not None:
                job["stage"] = stage
            if detail is not None:
                job["detail"] = detail
            if log:
                job["log"].append(str(log)[-1200:])
                job["log"] = job["log"][-30:]
            job.update(extra)
            job["updated_at"] = time.time()

    def _progress_cb(self, job_id: str):
        def cb(progress: int, stage: str, detail: str = ""):
            self._update(job_id, progress=progress, stage=stage, detail=detail, log=f"{stage}: {detail}" if detail else stage)
        return cb

    def start(
        self, *, category: str, quality: str, texture_preset: str,
        image_path: str | Path | None = None, prompt: str | None = None,
        display_name: str | None = None, low_vram: bool = False,
    ) -> str:
        job_id, folder = self._new("do_vat_3d")
        saved_image = None
        if image_path:
            src = Path(image_path)
            saved_image = folder / ("input" + (src.suffix.lower() or ".png"))
            import shutil as _shutil
            _shutil.copy2(src, saved_image)

        def worker():
            self._update(job_id, status="running", progress=2, stage="Bắt đầu", detail="")
            try:
                result = self.service.tao_do_vat(
                    category=category, quality=quality, texture_preset=texture_preset,
                    work_dir=folder / "work", image_path=saved_image, prompt=prompt,
                    low_vram=low_vram, progress=self._progress_cb(job_id),
                    cancel_event=self._cancel_events[job_id],
                )
                ten = sanitize_ten_asset(display_name or result["category_label"])
                meta = {
                    "category": result["category"],
                    "name": display_name or result["category_label"],
                    "engine": result["engine"],
                    "quality": result["quality"],
                    "has_texture": result["has_texture"],
                    "poly_count": result["triangle_count"],
                    "vertices": result["vertex_count"],
                    "dimensions": result["dimensions"],
                    "pivot": result["pivot"],
                    "recommended_scale": result["recommended_scale"],
                    "game_ready": False,
                    "source": "prompt" if prompt else "image",
                    "prompt": prompt,
                    "texture_preset": result["texture_preset"],
                    "texture_error": result["texture_error"],
                    "engine_reason": result["engine_reason"],
                    "device": result.get("device"),
                    "timings": result["timings"],
                    "suggested_filename": f"{ten}.glb",
                }
                payload = self.workspace.create_asset(result["model_path"], None, meta)
                # asset.json rieng theo dung contract GameAsset3D, doc lap voi
                # meta.json noi bo cua Model3DWorkspace (co the doi cau truc sau).
                asset_folder = self.workspace.root / payload["asset_id"]
                contract = game_asset_from_metadata(
                    {**meta, "asset_id": payload["asset_id"]},
                    glb_path=asset_folder / payload["model"],
                    thumbnail_path=None,
                )
                (asset_folder / "asset.json").write_text(
                    json.dumps(contract.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (folder / "job.json").write_text(
                    json.dumps({"job_id": job_id, **meta, "asset_id": payload["asset_id"]}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._update(job_id, status="done", progress=100, stage="Hoàn tất", detail="Đồ vật 3D đã tạo xong", result=payload)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:  # noqa: BLE001
                self._update(job_id, status="error", stage="Lỗi", detail=str(exc), error=str(exc))

        threading.Thread(target=worker, daemon=True, name=f"aivf-dovat3d-{job_id[:8]}").start()
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
            job["detail"] = "Giữ nguyên shape.glb đã tạo (nếu có), chỉ dừng bước đang chạy"
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
                raise ValueError("Không tìm thấy job đồ vật 3D")
            job = dict(self._jobs[job_id])
            job["log"] = list(job.get("log") or [])
            return job
