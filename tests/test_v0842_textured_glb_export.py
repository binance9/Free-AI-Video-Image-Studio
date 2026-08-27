import json
import struct
from pathlib import Path

from PIL import Image

from app.modules.nhan_vat_3d.textured_glb_export import (
    convert_textured_obj_to_glb,
    glb_has_embedded_texture,
)


def test_textured_obj_is_packed_as_glb(tmp_path):
    obj = tmp_path / "mesh.obj"
    obj.write_text(
        "v 0 0 0\n"
        "v 1 0 0\n"
        "v 0 1 0\n"
        "vt 0 0\n"
        "vt 1 0\n"
        "vt 0 1\n"
        "vn 0 0 1\n"
        "f 1/1/1 2/2/1 3/3/1\n",
        encoding="utf-8",
    )
    texture = tmp_path / "texture.png"
    Image.new("RGBA", (8, 8), (220, 40, 80, 255)).save(texture)
    out = tmp_path / "mesh.glb"
    convert_textured_obj_to_glb(obj, texture, out)
    assert out.exists()
    assert glb_has_embedded_texture(out)
    data = out.read_bytes()
    json_len, _ = struct.unpack_from("<II", data, 12)
    doc = json.loads(data[20:20 + json_len].decode("utf-8").rstrip("\\x00 "))
    assert doc["images"][0]["mimeType"] == "image/png"
    assert doc["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"] == 0


def test_backend_uses_obj_for_baked_texture():
    root = Path(__file__).resolve().parents[1]
    code = (root / "app/modules/nhan_vat_3d/triposr_backend.py").read_text(encoding="utf-8")
    assert 'save_format = "obj" if texture else "glb"' in code
    assert 'Đóng gói GLB có màu' in code
    assert 'textured_glb_converter' in code
