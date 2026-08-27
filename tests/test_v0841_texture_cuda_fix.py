from app.modules.nhan_vat_3d.texture_cuda_patch import (
    PATCH_MARKER,
    apply_texture_cuda_patch,
)

UPSTREAM_SAMPLE = """import numpy as np
import torch

def positions_to_colors(model, scene_code, positions_texture, texture_resolution):
    positions = torch.tensor(positions_texture.reshape(-1, 4)[:, :-1])
    with torch.no_grad():
        queried_grid = model.renderer.query_triplane(
            model.decoder,
            positions,
            scene_code,
        )
    rgb_f = queried_grid["color"].numpy().reshape(-1, 3)
    rgba_f = np.insert(rgb_f, 3, positions_texture.reshape(-1, 4)[:, -1], axis=1)
    rgba_f[rgba_f[:, -1] == 0.0] = [0, 0, 0, 0]
    return rgba_f.reshape(texture_resolution, texture_resolution, 4)

def bake_texture(mesh, model, scene_code, texture_resolution):
    return {}
"""


def test_patch_rewrites_cuda_device_and_numpy(tmp_path):
    triposr = tmp_path / "TripoSR"
    target = triposr / "tsr" / "bake_texture.py"
    target.parent.mkdir(parents=True)
    target.write_text(UPSTREAM_SAMPLE, encoding="utf-8")

    result = apply_texture_cuda_patch(triposr)
    assert result["ok"] is True
    assert result["patched"] is True

    fixed = target.read_text(encoding="utf-8")
    assert PATCH_MARKER in fixed
    assert "device=scene_device" in fixed
    assert "dtype=scene_dtype" in fixed
    assert ".cpu()" in fixed
    assert ".numpy()" in fixed
    assert target.with_suffix(".py.aivf_backup").exists()


def test_patch_is_idempotent(tmp_path):
    triposr = tmp_path / "TripoSR"
    target = triposr / "tsr" / "bake_texture.py"
    target.parent.mkdir(parents=True)
    target.write_text(UPSTREAM_SAMPLE, encoding="utf-8")
    assert apply_texture_cuda_patch(triposr)["patched"] is True
    second = apply_texture_cuda_patch(triposr)
    assert second["ok"] is True
    assert second["patched"] is False
