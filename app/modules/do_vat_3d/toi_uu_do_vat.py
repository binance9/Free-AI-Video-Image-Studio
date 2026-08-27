"""Chuan hoa pivot/mesh cho GLB do_vat_3d bang cach goi lai
app/modules/nhan_vat_3d/mesh_finish.py qua subprocess - script nay HOAN TOAN
generic (auto_upright + center_and_ground + smooth, khong co logic nhan vat
nao ben trong), nen tai dung truc tiep thay vi viet lai.

TripoSR (engine "quick") da tu goi script nay ben trong generate() cua no
(xem app/modules/nhan_vat_3d/triposr_backend.py::_finish_mesh) nen KHONG can
goi lai o day. Character HD (engine "character_hd") thi chua co buoc nay
trong pipeline nhan vat hien tai, nen do_vat_3d phai tu goi rieng de dam bao
moi asset (bat ke engine nao) deu co pivot bottom_center nhat quan.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .kiem_tra_do_vat import kiem_tra_glb

_MESH_FINISH_SCRIPT = Path(__file__).resolve().parent.parent / "nhan_vat_3d" / "mesh_finish.py"
_MESH_DECIMATE_SCRIPT = Path(__file__).resolve().parent.parent / "nhan_vat_3d" / "mesh_decimate.py"

BBOX_VOLUME_MIN_RATIO = 0.70
BBOX_VOLUME_MAX_RATIO = 1.30


def can_chuan_hoa_pivot(engine: str) -> bool:
    """TripoSR ('quick') da tu chuan hoa pivot ben trong generate(); chi
    Character HD ('character_hd') can chuan hoa them o day."""
    return engine == "character_hd"


def chuan_hoa_pivot(glb_path: str | Path, runtime_python: str | Path) -> bool:
    """Chay mesh_finish.py (center_and_ground + auto_upright) tren glb_path
    bang python cua venv co trimesh (runtime_python). Tra ve True neu chay
    thanh cong va thay the file, False neu bo qua (khong co script/venv)."""
    glb_path = Path(glb_path)
    if not _MESH_FINISH_SCRIPT.exists() or not Path(runtime_python).exists():
        return False
    finished = glb_path.with_name(glb_path.stem + "_pivot.glb")
    cmd = [str(runtime_python), str(_MESH_FINISH_SCRIPT), str(glb_path), str(finished)]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode == 0 and finished.exists():
        finished.replace(glb_path)
        return True
    return False


@dataclass(frozen=True)
class KetQuaToiUuSoMat:
    optimize_applied: bool
    original_triangle_count: int
    optimized_triangle_count: int
    poly_target: int
    poly_target_met: bool
    optimization_ratio: float  # optimized/original, 1.0 neu khong optimize
    optimizer: str
    error: str | None = None


def _bbox_volume(dimensions: dict | None) -> float | None:
    if not dimensions:
        return None
    try:
        return float(dimensions["x"]) * float(dimensions["y"]) * float(dimensions["z"])
    except (KeyError, TypeError, ValueError):
        return None


def toi_uu_so_mat(
    input_glb: str | Path,
    output_glb: str | Path,
    target_triangles: int,
    *,
    runtime_python: str | Path,
    tolerance: float = 0.15,
    preserve_boundary: bool = True,  # best-effort: vertex clustering khong remap UV/boundary rieng, tham so nay giu de tuong thich interface
) -> KetQuaToiUuSoMat:
    """Giam so tam giac cua input_glb ve gan target_triangles (+-tolerance),
    ghi ra output_glb MOI - KHONG bao gio de mat input_glb. Neu optimizer loi,
    timeout, hoac ket qua khong an toan (bbox sup/phong bat thuong, mesh
    rong, NaN) -> fallback: copy nguyen input sang output, optimize_applied=False,
    error ghi ro ly do. Khong lam fail toan job vi decimate loi."""
    input_glb = Path(input_glb)
    output_glb = Path(output_glb)

    goc = kiem_tra_glb(input_glb)
    if not goc.hop_le:
        shutil.copy2(input_glb, output_glb)
        return KetQuaToiUuSoMat(
            optimize_applied=False, original_triangle_count=goc.triangle_count,
            optimized_triangle_count=goc.triangle_count, poly_target=int(target_triangles),
            poly_target_met=False, optimization_ratio=1.0, optimizer="none",
            error="Bỏ qua optimize: shape gốc không hợp lệ (" + "; ".join(goc.ly_do_loi) + ")",
        )

    def _fallback(error: str) -> KetQuaToiUuSoMat:
        shutil.copy2(input_glb, output_glb)
        return KetQuaToiUuSoMat(
            optimize_applied=False, original_triangle_count=goc.triangle_count,
            optimized_triangle_count=goc.triangle_count, poly_target=int(target_triangles),
            poly_target_met=False, optimization_ratio=1.0, optimizer="none", error=error,
        )

    if not _MESH_DECIMATE_SCRIPT.exists():
        return _fallback("Optimize failed, using original mesh: thiếu mesh_decimate.py")
    if not Path(runtime_python).exists():
        return _fallback("Optimize failed, using original mesh: chưa cài Character HD runtime (cần trimesh)")

    candidate = output_glb.with_name(output_glb.stem + "_candidate.glb")
    cmd = [str(runtime_python), str(_MESH_DECIMATE_SCRIPT), str(input_glb), str(candidate),
           str(int(target_triangles)), "--tolerance", str(float(tolerance))]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        return _fallback("Optimize failed, using original mesh: decimate quá 10 phút")

    if done.returncode != 0 or not candidate.exists():
        detail = (done.stderr or done.stdout or "").strip()[-500:]
        return _fallback(f"Optimize failed, using original mesh: {detail}")

    stats = None
    for line in reversed(done.stdout.splitlines()):
        if line.startswith("AIVF_MESH_DECIMATE_OK "):
            try:
                stats = json.loads(line[len("AIVF_MESH_DECIMATE_OK "):])
            except Exception:
                stats = None
            break
    if stats is None:
        candidate.unlink(missing_ok=True)
        return _fallback("Optimize failed, using original mesh: không đọc được kết quả decimate")

    moi = kiem_tra_glb(candidate)
    if not moi.hop_le:
        candidate.unlink(missing_ok=True)
        return _fallback("Optimize failed, using original mesh: GLB sau optimize không hợp lệ (" + "; ".join(moi.ly_do_loi) + ")")

    vol_goc = _bbox_volume(goc.dimensions)
    vol_moi = _bbox_volume(moi.dimensions)
    if vol_goc and vol_moi:
        ratio = vol_moi / vol_goc if vol_goc > 0 else 0.0
        if not (BBOX_VOLUME_MIN_RATIO <= ratio <= BBOX_VOLUME_MAX_RATIO):
            candidate.unlink(missing_ok=True)
            return _fallback(
                f"Optimize failed, using original mesh: bounding box lệch bất thường sau optimize "
                f"({ratio:.2f}x thể tích gốc, ngoài [{BBOX_VOLUME_MIN_RATIO}, {BBOX_VOLUME_MAX_RATIO}])"
            )

    candidate.replace(output_glb)
    optimized_triangle_count = moi.triangle_count
    poly_target_met = bool(
        optimized_triangle_count > 0
        and target_triangles * (1 - tolerance) <= optimized_triangle_count <= target_triangles * (1 + tolerance)
    )
    ratio = (optimized_triangle_count / goc.triangle_count) if goc.triangle_count else 1.0
    return KetQuaToiUuSoMat(
        optimize_applied=bool(stats.get("optimized", optimized_triangle_count < goc.triangle_count)),
        original_triangle_count=goc.triangle_count,
        optimized_triangle_count=optimized_triangle_count,
        poly_target=int(target_triangles),
        poly_target_met=poly_target_met,
        optimization_ratio=round(ratio, 4),
        optimizer=str(stats.get("optimizer", "trimesh-vertex-clustering")),
        error=None,
    )
