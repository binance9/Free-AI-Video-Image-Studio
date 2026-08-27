"""Pack TripoSR's textured OBJ + PNG into one GLB with embedded texture.

This module is intentionally standalone and is executed by data/runtime3d/venv.
It does not add trimesh as a dependency of the main FastAPI Python runtime.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import trimesh
from PIL import Image


def glb_has_embedded_texture(path: str | Path) -> bool:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        return False
    json_len, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        return False
    doc = json.loads(data[20:20 + json_len].decode("utf-8").rstrip("\\x00 "))
    return bool(doc.get("images") and doc.get("textures") and doc.get("materials"))


def convert_textured_obj_to_glb(obj_path: str | Path, texture_path: str | Path, output_path: str | Path) -> Path:
    obj_path = Path(obj_path).resolve()
    texture_path = Path(texture_path).resolve()
    output_path = Path(output_path).resolve()
    if not obj_path.exists():
        raise FileNotFoundError(f"Không tìm thấy OBJ texture: {obj_path}")
    if not texture_path.exists():
        raise FileNotFoundError(f"Không tìm thấy texture PNG: {texture_path}")

    loaded = trimesh.load(obj_path, force="mesh", process=False, maintain_order=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise RuntimeError("OBJ tạm không đọc được thành một mesh")
    uv = getattr(loaded.visual, "uv", None)
    if uv is None or len(uv) != len(loaded.vertices):
        raise RuntimeError("OBJ tạm không có UV hợp lệ để gắn texture")

    image = Image.open(texture_path).convert("RGBA")
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=image,
        metallicFactor=0.0,
        roughnessFactor=1.0,
    )
    loaded.visual = trimesh.visual.texture.TextureVisuals(
        uv=uv,
        material=material,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    loaded.export(output_path, file_type="glb")

    if not output_path.exists() or output_path.stat().st_size < 512:
        raise RuntimeError("Đóng gói GLB thất bại hoặc file quá nhỏ")
    if not glb_has_embedded_texture(output_path):
        raise RuntimeError("GLB tạo ra chưa chứa texture nhúng")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("obj")
    parser.add_argument("texture")
    parser.add_argument("output")
    args = parser.parse_args()
    out = convert_textured_obj_to_glb(args.obj, args.texture, args.output)
    print(f"AIVF_TEXTURED_GLB_OK {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
