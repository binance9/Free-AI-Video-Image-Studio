"""Validate file GLB nhe - CHI dung thu vien chuan (struct + json), KHONG can
trimesh (khong co san trong venv chinh, chi co trong venv rieng cua TripoSR/
Hunyuan) va KHONG can Blender. Doc truc tiep binary GLB + JSON chunk theo
dung glTF 2.0 spec de lay bounding box / triangle count tu accessor.min/max,
khong phai doan mo.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

MIN_FILE_SIZE_BYTES = 200  # GLB hop le toi thieu phai co header + 1 mesh nho


class GlbKhongHopLe(ValueError):
    pass


@dataclass
class KetQuaKiemTraGlb:
    hop_le: bool
    ly_do_loi: list[str] = field(default_factory=list)
    triangle_count: int = 0
    vertex_count: int = 0
    dimensions: dict | None = None  # {"x":.., "y":.., "z":..}
    has_texture: bool = False
    mesh_count: int = 0
    primitive_count: int = 0


def _read_glb_chunks(path: Path) -> tuple[dict, bytes | None]:
    data = path.read_bytes()
    if len(data) < 20:
        raise GlbKhongHopLe("File quá nhỏ, không đủ header GLB")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise GlbKhongHopLe("File không đúng định dạng GLB (thiếu magic 'glTF')")
    offset = 12
    json_chunk = None
    bin_chunk = None
    while offset < len(data):
        if offset + 8 > len(data):
            break
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        if chunk_end > len(data):
            break
        payload = data[chunk_start:chunk_end]
        if chunk_type == b"JSON":
            json_chunk = payload
        elif chunk_type == b"BIN\x00":
            bin_chunk = payload
        offset = chunk_end
    if json_chunk is None:
        raise GlbKhongHopLe("File GLB không có JSON chunk hợp lệ")
    try:
        doc = json.loads(json_chunk.decode("utf-8"))
    except Exception as exc:
        raise GlbKhongHopLe(f"JSON chunk trong GLB không đọc được: {exc}") from exc
    return doc, bin_chunk


def kiem_tra_glb(path: str | Path) -> KetQuaKiemTraGlb:
    path = Path(path)
    errors: list[str] = []

    if not path.exists():
        return KetQuaKiemTraGlb(hop_le=False, ly_do_loi=["File GLB không tồn tại"])
    size = path.stat().st_size
    if size < MIN_FILE_SIZE_BYTES:
        errors.append(f"File quá nhỏ ({size} bytes) - nghi ngờ export thất bại")

    try:
        doc, _bin = _read_glb_chunks(path)
    except GlbKhongHopLe as exc:
        return KetQuaKiemTraGlb(hop_le=False, ly_do_loi=[str(exc)])

    meshes = doc.get("meshes") or []
    if not meshes:
        errors.append("GLB không có mesh nào")

    accessors = doc.get("accessors") or []
    triangle_count = 0
    vertex_count = 0
    primitive_count = 0
    mins: list[list[float]] = []
    maxs: list[list[float]] = []

    for mesh in meshes:
        for prim in mesh.get("primitives") or []:
            primitive_count += 1
            mode = prim.get("mode", 4)  # 4 = TRIANGLES (mac dinh glTF)
            pos_idx = (prim.get("attributes") or {}).get("POSITION")
            if pos_idx is not None and pos_idx < len(accessors):
                acc = accessors[pos_idx]
                vertex_count += int(acc.get("count", 0))
                if acc.get("min") and acc.get("max"):
                    mins.append(acc["min"])
                    maxs.append(acc["max"])
            idx_idx = prim.get("indices")
            if mode == 4:  # chi dem tam giac cho primitive kieu TRIANGLES
                if idx_idx is not None and idx_idx < len(accessors):
                    triangle_count += int(accessors[idx_idx].get("count", 0)) // 3
                elif pos_idx is not None and pos_idx < len(accessors):
                    triangle_count += int(accessors[pos_idx].get("count", 0)) // 3

    if primitive_count == 0:
        errors.append("GLB không có primitive nào (mesh rỗng)")
    if triangle_count <= 0:
        errors.append("Triangle count = 0 - mesh rỗng hoặc export lỗi")

    dimensions = None
    if mins and maxs:
        gx0 = min(m[0] for m in mins); gx1 = max(m[0] for m in maxs)
        gy0 = min(m[1] for m in mins); gy1 = max(m[1] for m in maxs)
        gz0 = min(m[2] for m in mins); gz1 = max(m[2] for m in maxs)
        dims = {"x": gx1 - gx0, "y": gy1 - gy0, "z": gz1 - gz0}
        for axis, value in dims.items():
            if value != value:  # NaN check (NaN != NaN theo IEEE754)
                errors.append(f"Bounding box trục {axis} là NaN")
            elif value <= 0 or value > 10_000:
                errors.append(f"Bounding box trục {axis} vô lý: {value}")
        dimensions = dims
    else:
        errors.append("Không đọc được bounding box (accessor thiếu min/max)")

    materials = doc.get("materials") or []
    images = doc.get("images") or []
    textures = doc.get("textures") or []
    has_texture = bool(materials) and bool(images) and bool(textures)

    return KetQuaKiemTraGlb(
        hop_le=len(errors) == 0,
        ly_do_loi=errors,
        triangle_count=triangle_count,
        vertex_count=vertex_count,
        dimensions=dimensions,
        has_texture=has_texture,
        mesh_count=len(meshes),
        primitive_count=primitive_count,
    )
