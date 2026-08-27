from __future__ import annotations

import re
from pathlib import Path

PATCH_MARKER = "AIVF_TEXTURE_CUDA_PATCH_0_8_4_1"

FIXED_FUNCTION = (
    "def positions_to_colors(model, scene_code, positions_texture, texture_resolution):\n"
    "    # AIVF_TEXTURE_CUDA_PATCH_0_8_4_1\n"
    "    scene_device = scene_code.device\n"
    "    scene_dtype = scene_code.dtype if scene_code.is_floating_point() else torch.float32\n"
    "    positions = torch.as_tensor(\n"
    "        positions_texture.reshape(-1, 4)[:, :-1],\n"
    "        device=scene_device,\n"
    "        dtype=scene_dtype,\n"
    "    )\n"
    "    with torch.no_grad():\n"
    "        queried_grid = model.renderer.query_triplane(\n"
    "            model.decoder,\n"
    "            positions,\n"
    "            scene_code,\n"
    "        )\n"
    "    rgb_f = (\n"
    "        queried_grid['color']\n"
    "        .detach()\n"
    "        .float()\n"
    "        .cpu()\n"
    "        .numpy()\n"
    "        .reshape(-1, 3)\n"
    "    )\n"
    "    rgba_f = np.insert(\n"
    "        rgb_f,\n"
    "        3,\n"
    "        positions_texture.reshape(-1, 4)[:, -1],\n"
    "        axis=1,\n"
    "    )\n"
    "    rgba_f[rgba_f[:, -1] == 0.0] = [0, 0, 0, 0]\n"
    "    return rgba_f.reshape(texture_resolution, texture_resolution, 4)\n\n"
)


def apply_texture_cuda_patch(triposr_dir: str | Path) -> dict:
    triposr_dir = Path(triposr_dir).resolve()
    target = triposr_dir / "tsr" / "bake_texture.py"
    if not target.exists():
        return {"ok": False, "patched": False, "message": f"Không tìm thấy {target}"}

    text = target.read_text(encoding="utf-8")
    if PATCH_MARKER in text:
        return {"ok": True, "patched": False, "message": "Texture CUDA patch đã có"}

    pattern = re.compile(
        r"def positions_to_colors\(model,\s*scene_code,\s*positions_texture,\s*texture_resolution\):"
        r".*?(?=\ndef bake_texture\()",
        re.S,
    )
    match = pattern.search(text)
    if not match:
        return {
            "ok": False,
            "patched": False,
            "message": "Không nhận ra hàm positions_to_colors của TripoSR",
        }

    backup = target.with_suffix(".py.aivf_backup")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    target.write_text(
        text[:match.start()] + FIXED_FUNCTION + text[match.end():],
        encoding="utf-8",
    )
    return {"ok": True, "patched": True, "message": "Đã vá TripoSR texture CUDA/device/dtype"}
