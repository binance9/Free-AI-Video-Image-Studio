"""Dieu phoi pipeline ANH/PROMPT -> DO VAT 3D -> GLB, tai su dung engine that
da co o app.modules.nhan_vat_3d (TripoSR, Hunyuan3D/Character-HD) qua
Local3DService - KHONG duplicate business logic dung mesh. Phan rieng cua
module nay: chon category, chon engine, preprocess rieng cho do vat, tach
stage SHAPE/TEXTURE (giu shape neu texture loi), chuan hoa pivot, validate
GLB nhe, va build metadata/asset contract.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.core.shared_services import heavy_gpu_job_lock
from app.modules.nhan_vat_3d.service import Local3DService

from .chon_engine import chon_engine_do_vat
from .kiem_tra_do_vat import kiem_tra_glb
from .phan_loai_do_vat import validate_category, validate_quality, validate_texture
from .toi_uu_do_vat import can_chuan_hoa_pivot, chuan_hoa_pivot, toi_uu_so_mat
from .xu_ly_anh_dau_vao import chuan_hoa_anh_do_vat
from .cau_hinh_do_vat import DANH_MUC, TEXTURE_PRESETS, TEXTURE_TIMEOUT_SECONDS
from .prompt_do_vat import tao_prompt_concept_do_vat

_TEXTURE_TIMEOUT_MARKERS = ("quá thời gian tối đa", "không có heartbeat")


class DoVat3DService:
    def __init__(self, triposr_dir: str | Path, model_cache: str | Path, image_service, root: str | Path):
        # Tai su dung nguyen Local3DService cua nhan_vat_3d - class nay VON DA
        # generic (khong co logic rieng cho nhan vat ben trong), nen khong
        # can/khong nen viet lai. Chi khac: image_service la cua tao_anh_ai
        # (khong phai nhan_vat_2d), va workspace/output rieng cua do_vat_3d.
        self.engine_service = Local3DService(triposr_dir, model_cache, image_service, root)

    def status(self) -> dict:
        return self.engine_service.status()

    def tao_do_vat(
        self,
        *,
        category: str,
        quality: str,
        texture_preset: str,
        work_dir: str | Path,
        image_path: str | Path | None = None,
        prompt: str | None = None,
        low_vram: bool = False,
        progress=None,
        cancel_event=None,
    ) -> dict:
        if not image_path and not prompt:
            raise ValueError("Cần cung cấp ảnh hoặc prompt")
        cat_key = validate_category(category)
        quality_key = validate_quality(quality)
        texture_key = validate_texture(texture_preset)
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

        lua_chon = chon_engine_do_vat(cat_key, quality_key, low_vram=low_vram)
        if progress:
            progress(2, "Chọn engine", f"Engine: {lua_chon.engine_label} · {lua_chon.reason}")

        timings: dict[str, float] = {}
        t_start = time.time()

        # ---- STAGE 1: PREPROCESS + SHAPE (bat buoc texture=False de tach stage) ----
        t0 = time.time()
        image_for_texture: Path
        if prompt:
            if self.engine_service.image_service is None:
                raise ValueError("AI ảnh local chưa được nối với đồ vật 3D")
            concept_prompt = tao_prompt_concept_do_vat(prompt, cat_key)
            concept_path = work_dir / "concept.png"
            if progress:
                progress(5, "Tạo concept 2D", "Đang gọi tao_anh_ai để tạo ảnh concept đồ vật từ prompt…")
            with heavy_gpu_job_lock(owner="do_vat_3d", cancel_event=cancel_event,
                                     on_wait=lambda _w: progress and progress(5, "Đang chờ GPU", "Có job 3D khác đang chạy…")):
                concept_bytes = self.engine_service.image_service.generate(
                    concept_prompt,
                    style="product",
                    size="1024x1024",
                    quality="high",
                    cancel_event=cancel_event,
                )
            concept_path.write_bytes(concept_bytes)
            if progress:
                progress(12, "Concept đã xong", "Đang dựng shape 3D từ concept đồ vật…")
            with heavy_gpu_job_lock(owner="do_vat_3d", cancel_event=cancel_event,
                                     on_wait=lambda _w: progress and progress(12, "Đang chờ GPU", "Có job 3D khác đang chạy…")):
                shape_result = self.engine_service.from_image(
                    concept_path, work_dir, texture=False, backend=lua_chon.engine,
                    resolution=lua_chon.resolution, mesh_profile=lua_chon.mesh_profile,
                    progress=progress, cancel_event=cancel_event,
                )
            shape_result["concept_path"] = concept_path
            shape_result["concept_prompt_used"] = concept_prompt
            image_for_texture = concept_path
            preprocess_seconds = 0.0  # concept da duoc AI ve san, khong can crop/normalize them
        else:
            t_pre = time.time()
            preprocessed = work_dir / "preprocessed.png"
            chuan_hoa_anh_do_vat(image_path, preprocessed)
            preprocess_seconds = time.time() - t_pre
            if progress:
                progress(8, "Đã chuẩn hoá ảnh", "Crop quanh vật thể, đưa lên canvas vuông")
            with heavy_gpu_job_lock(owner="do_vat_3d", cancel_event=cancel_event,
                                     on_wait=lambda _w: progress and progress(8, "Đang chờ GPU", "Có job 3D khác đang chạy…")):
                shape_result = self.engine_service.from_image(
                    preprocessed, work_dir, texture=False, backend=lua_chon.engine,
                    resolution=lua_chon.resolution, mesh_profile=lua_chon.mesh_profile,
                    progress=progress, cancel_event=cancel_event,
                )
            image_for_texture = preprocessed
        timings["preprocess_seconds"] = round(preprocess_seconds, 2)
        timings["shape_seconds"] = round(time.time() - t0, 2)

        shape_glb = work_dir / "shape.glb"
        shutil.copy2(shape_result["model_path"], shape_glb)

        if can_chuan_hoa_pivot(lua_chon.engine):
            if progress:
                progress(45, "Chuẩn hoá pivot", "Đưa model về pivot bottom-center…")
            chuan_hoa_pivot(shape_glb, self.engine_service.character_hd.python)

        # ---- STAGE 2: ENFORCE POLY TARGET tren SHAPE (truoc khi to mau, vi
        # decimate bang vertex-clustering khong remap UV) - khong bao gio de
        # mat shape.glb goc, chi ghi ra optimized.glb rieng (section 3, 4, 5). ----
        t_opt = time.time()
        if progress:
            progress(50, "Tối ưu số mặt", f"Đang giảm poly về ~{lua_chon.poly_target:,} tam giác…")
        optimized_glb = work_dir / "optimized.glb"
        toi_uu_ket_qua = toi_uu_so_mat(
            shape_glb, optimized_glb, lua_chon.poly_target,
            runtime_python=self.engine_service.character_hd.python,
            tolerance=lua_chon.poly_tolerance,
        )
        timings["optimize_seconds"] = round(time.time() - t_opt, 2)
        mesh_for_texture = optimized_glb if toi_uu_ket_qua.optimize_applied else shape_glb
        if progress:
            if toi_uu_ket_qua.optimize_applied:
                progress(58, "Đã tối ưu số mặt",
                          f"{toi_uu_ket_qua.original_triangle_count:,} → {toi_uu_ket_qua.optimized_triangle_count:,} tam giác")
            else:
                progress(58, "Giữ nguyên số mặt gốc", toi_uu_ket_qua.error or "Không cần/không tối ưu được")

        # ---- STAGE 3 (optional): TEXTURE tren mesh da toi uu - khong duoc
        # lam mat shape/optimized mesh neu loi hoac timeout (section 17-18). ----
        final_glb = mesh_for_texture
        has_texture = False
        texture_error: str | None = None
        texture_timed_out = False
        texture_seconds = 0.0
        if TEXTURE_PRESETS[texture_key]["apply_texture"]:
            t1 = time.time()
            texture_quality = TEXTURE_PRESETS[texture_key].get("texture_quality", "lite")
            timeout_seconds = TEXTURE_TIMEOUT_SECONDS.get(texture_quality, 600)
            if progress:
                progress(60, "Tô màu", f"Đang tô màu GLB ({TEXTURE_PRESETS[texture_key]['label']})…")
            try:
                with heavy_gpu_job_lock(owner="do_vat_3d", cancel_event=cancel_event,
                                         on_wait=lambda _w: progress and progress(60, "Đang chờ GPU", "Có job 3D khác đang chạy…")):
                    texture_result = self.engine_service.colorize_existing(
                        mesh_for_texture, image_for_texture, work_dir / "texture_out",
                        progress=progress, cancel_event=cancel_event,
                        timeout_seconds=timeout_seconds, idle_timeout_seconds=timeout_seconds,
                    )
                textured_glb = work_dir / "textured.glb"
                shutil.copy2(texture_result["model_path"], textured_glb)
                final_glb = textured_glb
                has_texture = True
            except Exception as exc:  # noqa: BLE001 - phai giu mesh_for_texture du texture loi/timeout kieu gi
                texture_error = str(exc)
                texture_timed_out = any(marker in texture_error for marker in _TEXTURE_TIMEOUT_MARKERS)
                if progress:
                    progress(60, "Tô màu lỗi - giữ shape/mesh đã tối ưu", texture_error)
            texture_seconds = time.time() - t1
        timings["texture_seconds"] = round(texture_seconds, 2)

        # ---- STAGE 4: VALIDATE (khong can Blender/trimesh) ----
        t2 = time.time()
        if progress:
            progress(92, "Kiểm tra GLB", "Đang kiểm tra mesh/bounding box…")
        kiem_tra = kiem_tra_glb(final_glb)
        timings["validate_seconds"] = round(time.time() - t2, 2)
        timings["total_seconds"] = round(time.time() - t_start, 2)

        if not kiem_tra.hop_le:
            raise ValueError("GLB không hợp lệ sau khi tạo: " + "; ".join(kiem_tra.ly_do_loi))

        cat = DANH_MUC[cat_key]
        return {
            "model_path": final_glb,
            "shape_path": shape_glb,
            "optimized_path": optimized_glb if toi_uu_ket_qua.optimize_applied else None,
            "best_output_path": final_glb,
            "category": cat_key,
            "category_label": cat.ten_hien_thi,
            "pivot": cat.pivot,
            "recommended_scale": {"min": cat.recommended_scale_min, "max": cat.recommended_scale_max, "note": cat.scale_note},
            "quality": quality_key,
            "texture_preset": texture_key,
            "has_texture": has_texture,
            "texture_error": texture_error,
            "texture_timed_out": texture_timed_out,
            "engine": lua_chon.engine,
            "engine_label": lua_chon.engine_label,
            "engine_reason": lua_chon.reason,
            "triangle_count": kiem_tra.triangle_count,
            "vertex_count": kiem_tra.vertex_count,
            "dimensions": kiem_tra.dimensions,
            "device": shape_result.get("device"),
            "concept_prompt_used": shape_result.get("concept_prompt_used"),
            "timings": timings,
            "poly": {
                "original_triangle_count": toi_uu_ket_qua.original_triangle_count,
                "optimized_triangle_count": toi_uu_ket_qua.optimized_triangle_count,
                "poly_target": toi_uu_ket_qua.poly_target,
                "poly_target_met": toi_uu_ket_qua.poly_target_met,
                "optimization_ratio": toi_uu_ket_qua.optimization_ratio,
                "optimizer": toi_uu_ket_qua.optimizer,
                "optimize_applied": toi_uu_ket_qua.optimize_applied,
                "optimize_error": toi_uu_ket_qua.error,
            },
        }

    def to_mau_lai(
        self,
        *,
        mesh_glb: str | Path,
        image_path: str | Path,
        work_dir: str | Path,
        texture_preset: str,
        progress=None,
        cancel_event=None,
    ) -> dict:
        """Retry CHI stage texture tren mesh da co (shape hoac optimized.glb
        cua job truoc) - KHONG dung lai preprocess/shape (section 25)."""
        texture_key = validate_texture(texture_preset)
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        mesh_glb = Path(mesh_glb)

        timings: dict[str, float] = {}
        t_start = time.time()
        has_texture = False
        texture_error: str | None = None
        texture_timed_out = False
        final_glb = mesh_glb

        if TEXTURE_PRESETS[texture_key]["apply_texture"]:
            texture_quality = TEXTURE_PRESETS[texture_key].get("texture_quality", "lite")
            timeout_seconds = TEXTURE_TIMEOUT_SECONDS.get(texture_quality, 600)
            if progress:
                progress(20, "Tô màu lại", f"Đang tô màu GLB ({TEXTURE_PRESETS[texture_key]['label']})…")
            try:
                with heavy_gpu_job_lock(owner="do_vat_3d", cancel_event=cancel_event,
                                         on_wait=lambda _w: progress and progress(20, "Đang chờ GPU", "Có job 3D khác đang chạy…")):
                    texture_result = self.engine_service.colorize_existing(
                        mesh_glb, image_path, work_dir / "texture_out",
                        progress=progress, cancel_event=cancel_event,
                        timeout_seconds=timeout_seconds, idle_timeout_seconds=timeout_seconds,
                    )
                textured_glb = work_dir / "textured.glb"
                shutil.copy2(texture_result["model_path"], textured_glb)
                final_glb = textured_glb
                has_texture = True
            except Exception as exc:  # noqa: BLE001
                texture_error = str(exc)
                texture_timed_out = any(marker in texture_error for marker in _TEXTURE_TIMEOUT_MARKERS)
        timings["texture_seconds"] = round(time.time() - t_start, 2)

        if progress:
            progress(90, "Kiểm tra GLB", "Đang kiểm tra mesh/bounding box…")
        kiem_tra = kiem_tra_glb(final_glb)
        timings["total_seconds"] = round(time.time() - t_start, 2)
        if not kiem_tra.hop_le:
            raise ValueError("GLB không hợp lệ sau khi tô màu lại: " + "; ".join(kiem_tra.ly_do_loi))

        return {
            "model_path": final_glb,
            "texture_preset": texture_key,
            "has_texture": has_texture,
            "texture_error": texture_error,
            "texture_timed_out": texture_timed_out,
            "triangle_count": kiem_tra.triangle_count,
            "vertex_count": kiem_tra.vertex_count,
            "dimensions": kiem_tra.dimensions,
            "timings": timings,
        }
