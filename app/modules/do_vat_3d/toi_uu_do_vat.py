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

import subprocess
from pathlib import Path

_MESH_FINISH_SCRIPT = Path(__file__).resolve().parent.parent / "nhan_vat_3d" / "mesh_finish.py"


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
