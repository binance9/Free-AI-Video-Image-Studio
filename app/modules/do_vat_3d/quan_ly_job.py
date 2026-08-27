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
                apply_texture_requested = bool(texture_preset and texture_preset != "none")
                is_partial = bool(result["texture_error"]) and apply_texture_requested and not result["has_texture"]
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
                    "texture_timed_out": result.get("texture_timed_out", False),
                    "engine_reason": result["engine_reason"],
                    "device": result.get("device"),
                    "timings": result["timings"],
                    "poly": result["poly"],
                    "best_output_path": str(result["best_output_path"]),
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
                # Luu lai de retry-texture dung lai dung mesh/anh nay, KHONG
                # dung lai shape (section 25-26).
                retry_info = {
                    "work_dir": str(folder / "work"),
                    "mesh_for_texture": str(result.get("optimized_path") or result["shape_path"]),
                    "image_for_texture": str(saved_image) if saved_image else str((folder / "work" / "concept.png")),
                    "category": category, "quality": quality, "display_name": display_name,
                }
                if is_partial:
                    self._update(job_id, status="partial_success", progress=100,
                                 stage="Hoàn tất một phần", detail="Shape 3D xong, tô màu chưa hoàn tất",
                                 result=payload, retry_info=retry_info)
                else:
                    self._update(job_id, status="done", progress=100, stage="Hoàn tất",
                                 detail="Đồ vật 3D đã tạo xong", result=payload, retry_info=retry_info)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:  # noqa: BLE001
                self._update(job_id, status="error", stage="Lỗi", detail=str(exc), error=str(exc))

        threading.Thread(target=worker, daemon=True, name=f"aivf-dovat3d-{job_id[:8]}").start()
        return job_id

    def retry_texture(self, job_id: str, texture_mode: str) -> None:
        """Chi chay lai stage texture tren mesh da co cua job_id (shape hoac
        optimized.glb) - KHONG dung lai preprocess/shape (section 25)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError("Không tìm thấy job đồ vật 3D")
            retry_info = job.get("retry_info")
            if not retry_info:
                raise ValueError("Job này chưa có dữ liệu để tô màu lại")
            if job.get("status") in {"queued", "running", "cancelling"}:
                raise ValueError("Job đang chạy, không thể tô màu lại lúc này")
            self._cancel_events[job_id] = threading.Event()

        mesh_for_texture = Path(retry_info["mesh_for_texture"])
        image_for_texture = Path(retry_info["image_for_texture"])
        if not mesh_for_texture.exists():
            raise ValueError("Không còn mesh đã tạo trước đó để tô màu lại")
        if not image_for_texture.exists():
            raise ValueError("Không còn ảnh tham chiếu trước đó để tô màu lại")

        self._update(job_id, status="running", progress=2, stage="Bắt đầu tô màu lại", detail="")

        def worker():
            try:
                result = self.service.to_mau_lai(
                    mesh_glb=mesh_for_texture, image_path=image_for_texture,
                    work_dir=Path(retry_info["work_dir"]) / f"retry_{uuid.uuid4().hex[:8]}",
                    texture_preset=texture_mode, progress=self._progress_cb(job_id),
                    cancel_event=self._cancel_events[job_id],
                )
                cat = retry_info["category"]
                display_name = retry_info.get("display_name")
                ten = sanitize_ten_asset(display_name or cat)
                meta = {
                    "category": cat, "name": display_name or cat, "quality": retry_info["quality"],
                    "has_texture": result["has_texture"], "poly_count": result["triangle_count"],
                    "vertices": result["vertex_count"], "dimensions": result["dimensions"],
                    "game_ready": False, "source": "retry_texture",
                    "texture_preset": result["texture_preset"], "texture_error": result["texture_error"],
                    "texture_timed_out": result.get("texture_timed_out", False),
                    "timings": result["timings"], "best_output_path": str(result["model_path"]),
                    "suggested_filename": f"{ten}.glb",
                }
                payload = self.workspace.create_asset(result["model_path"], None, meta)
                is_partial = bool(result["texture_error"]) and not result["has_texture"]
                if is_partial:
                    self._update(job_id, status="partial_success", progress=100,
                                 stage="Tô màu lại chưa xong", detail=result["texture_error"] or "", result=payload)
                else:
                    self._update(job_id, status="done", progress=100, stage="Hoàn tất tô màu lại",
                                 detail="Đã tô màu lại thành công", result=payload)
            except JobCancelled as exc:
                self._update(job_id, status="cancelled", stage="Đã dừng", detail=str(exc), error=None)
            except Exception as exc:  # noqa: BLE001
                self._update(job_id, status="error", stage="Lỗi", detail=str(exc), error=str(exc))

        threading.Thread(target=worker, daemon=True, name=f"aivf-dovat3d-retry-{job_id[:8]}").start()

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
