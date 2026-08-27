"""Unit test cho nhan_vat_game_ready.validate_game_ready - KHONG can Blender,
tu dung GLB toi thieu bang struct+json (cung phong cach voi
tests/test_do_vat_3d_unit.py::_build_minimal_glb) de test validator doc lap.

Chay: pytest -q tests/test_nhan_vat_game_ready_unit.py
"""
from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path

import pytest

from app.modules.nhan_vat_game_ready.validate_game_ready import (
    REQUIRED_CLIPS,
    validate_game_ready_glb,
)

# ---------- generic minimal-GLB builder with optional skin + animations ----------


def _pack_floats(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _build_game_ready_glb(
    path,
    *,
    with_skin: bool = True,
    with_joints_attr: bool = True,
    with_weights_attr: bool = True,
    weight_rows: list[list[float]] | None = None,
    clips: dict[str, str] | None = None,
    # clip name -> "motion" (2 differing keyframes), "static" (2 identical keyframes), or omit entirely
) -> None:
    """Build a tiny but structurally real glTF: 1 mesh (4 verts, 2 triangles),
    a 2-node skeleton (root -> bone1), a skin, and 0+ animation clips each
    with a single rotation channel targeting bone1."""
    clips = clips if clips is not None else {"idle": "motion", "run": "motion", "attack_01": "motion"}
    positions = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    indices = [0, 1, 2, 0, 1, 3]
    if weight_rows is None:
        weight_rows = [[1.0, 0.0, 0.0, 0.0]] * 4
    joints_rows = [[0, 0, 0, 0]] * 4

    buffers_bin = b""
    buffer_views = []
    accessors = []

    def add_buffer_view(data: bytes) -> int:
        nonlocal buffers_bin
        # 4-byte align
        pad = (4 - len(data) % 4) % 4
        offset = len(buffers_bin)
        buffers_bin += data + b"\x00" * pad
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data)})
        return len(buffer_views) - 1

    # POSITION
    pos_bytes = _pack_floats(positions)
    pos_view = add_buffer_view(pos_bytes)
    accessors.append({
        "bufferView": pos_view, "componentType": 5126, "count": 4, "type": "VEC3",
        "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0],
    })
    pos_acc = len(accessors) - 1

    # indices
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)
    idx_view = add_buffer_view(idx_bytes)
    accessors.append({"bufferView": idx_view, "componentType": 5123, "count": len(indices), "type": "SCALAR"})
    idx_acc = len(accessors) - 1

    attributes = {"POSITION": pos_acc}

    if with_joints_attr:
        joints_flat = [v for row in joints_rows for v in row]
        joints_bytes = struct.pack(f"<{len(joints_flat)}H", *joints_flat)
        joints_view = add_buffer_view(joints_bytes)
        accessors.append({"bufferView": joints_view, "componentType": 5123, "count": 4, "type": "VEC4"})
        attributes["JOINTS_0"] = len(accessors) - 1

    if with_weights_attr:
        weights_flat = [v for row in weight_rows for v in row]
        weights_bytes = _pack_floats(weights_flat)
        weights_view = add_buffer_view(weights_bytes)
        accessors.append({"bufferView": weights_view, "componentType": 5126, "count": 4, "type": "VEC4"})
        attributes["WEIGHTS_0"] = len(accessors) - 1

    nodes = [
        {"name": "root", "children": [1]},
        {"name": "bone1", "rotation": [0, 0, 0, 1]},
        {"name": "MeshNode", "mesh": 0, "skin": 0 if with_skin else None},
    ]
    if not with_skin:
        del nodes[2]["skin"]

    doc = {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0, 2]}],
        "scene": 0,
        "nodes": nodes,
        "meshes": [{"primitives": [{"attributes": attributes, "indices": idx_acc}]}],
    }

    if with_skin:
        # inverseBindMatrices: 2 identity 4x4 matrices (joints = [0, 1])
        ibm_flat = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] * 2
        ibm_bytes = _pack_floats([float(v) for v in ibm_flat])
        ibm_view = add_buffer_view(ibm_bytes)
        accessors.append({"bufferView": ibm_view, "componentType": 5126, "count": 2, "type": "MAT4"})
        doc["skins"] = [{"joints": [0, 1], "inverseBindMatrices": len(accessors) - 1}]

    animations = []
    for name, kind in clips.items():
        if kind is None:
            continue
        times_bytes = _pack_floats([0.0, 1.0])
        times_view = add_buffer_view(times_bytes)
        accessors.append({"bufferView": times_view, "componentType": 5126, "count": 2, "type": "SCALAR"})
        time_acc = len(accessors) - 1

        if kind == "motion":
            values = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.7071, 0.7071]  # identity -> 90deg quat
        else:  # "static"
            values = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        values_bytes = _pack_floats(values)
        values_view = add_buffer_view(values_bytes)
        accessors.append({"bufferView": values_view, "componentType": 5126, "count": 2, "type": "VEC4"})
        value_acc = len(accessors) - 1

        animations.append({
            "name": name,
            "samplers": [{"input": time_acc, "output": value_acc, "interpolation": "LINEAR"}],
            "channels": [{"sampler": 0, "target": {"node": 1, "path": "rotation"}}],
        })
    if animations:
        doc["animations"] = animations

    doc["buffers"] = [{"byteLength": len(buffers_bin)}]
    doc["bufferViews"] = buffer_views
    doc["accessors"] = accessors

    json_bytes = json.dumps(doc).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(buffers_bin)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total_len))
        f.write(struct.pack("<I4s", len(json_bytes), b"JSON"))
        f.write(json_bytes)
        f.write(struct.pack("<I4s", len(buffers_bin), b"BIN\x00"))
        f.write(buffers_bin)


@pytest.fixture
def tmp_glb_path():
    fd, path = tempfile.mkstemp(suffix=".glb")
    import os
    os.close(fd)
    yield Path(path)
    Path(path).unlink(missing_ok=True)


# ---------- tests ----------


def test_valid_fixture_passes_fully(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path)
    result = validate_game_ready_glb(tmp_glb_path)
    assert result.ok, result.errors
    assert result.animation_ok, result.warnings
    assert result.skins_count == 1
    assert result.joints_count == 2
    assert result.has_joints_attr and result.has_weights_attr
    assert result.weight_coverage == 1.0
    assert set(result.animations) == {"idle", "run", "attack_01"}


def test_missing_skin_fails(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, with_skin=False)
    result = validate_game_ready_glb(tmp_glb_path)
    assert not result.ok
    assert any("skin" in e.lower() for e in result.errors)


def test_missing_joints_attribute_fails(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, with_joints_attr=False)
    result = validate_game_ready_glb(tmp_glb_path)
    assert not result.ok
    assert any("JOINTS_0" in e for e in result.errors)


def test_missing_weights_attribute_fails(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, with_weights_attr=False)
    result = validate_game_ready_glb(tmp_glb_path)
    assert not result.ok
    assert any("WEIGHTS_0" in e for e in result.errors)


def test_all_zero_weights_fails_even_with_attribute_present(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, weight_rows=[[0.0, 0.0, 0.0, 0.0]] * 4)
    result = validate_game_ready_glb(tmp_glb_path)
    assert not result.ok
    assert result.weight_coverage == 0.0
    assert any("WEIGHTS_0" in e for e in result.errors)


def test_missing_animations_entirely_fails_animation_ok_but_not_mesh_ok(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, clips={})
    result = validate_game_ready_glb(tmp_glb_path)
    assert result.ok  # mesh/skin still valid
    assert not result.animation_ok
    for clip in REQUIRED_CLIPS:
        assert result.required_clips_present[clip] is False


def test_run_with_no_real_motion_fails_animation_ok():
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        path = Path(f.name)
    try:
        _build_game_ready_glb(path, clips={"idle": "motion", "run": "static", "attack_01": "motion"})
        result = validate_game_ready_glb(path)
        assert result.ok
        assert not result.animation_ok
        assert result.required_clips_present["run"] is True
        assert result.required_clips_animated["run"] is False
        assert any("run" in w.lower() for w in result.warnings)
    finally:
        path.unlink(missing_ok=True)


def test_attack_with_no_real_motion_fails_animation_ok():
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        path = Path(f.name)
    try:
        _build_game_ready_glb(path, clips={"idle": "motion", "run": "motion", "attack_01": "static"})
        result = validate_game_ready_glb(path)
        assert result.ok
        assert not result.animation_ok
        assert result.required_clips_animated["attack_01"] is False
    finally:
        path.unlink(missing_ok=True)


def test_clip_name_matching_is_case_insensitive(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, clips={"IDLE": "motion", "Run": "motion", "Attack_01": "motion"})
    result = validate_game_ready_glb(tmp_glb_path)
    assert result.ok and result.animation_ok
    assert all(result.required_clips_present.values())


def test_missing_file_fails_cleanly():
    result = validate_game_ready_glb("C:/does/not/exist/game_ready.glb")
    assert not result.ok
    assert result.errors


def test_partial_weight_coverage_below_threshold_fails(tmp_glb_path):
    # only 1 of 4 vertices weighted -> 25% coverage, well below 85% threshold
    rows = [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]]
    _build_game_ready_glb(tmp_glb_path, weight_rows=rows)
    result = validate_game_ready_glb(tmp_glb_path)
    assert not result.ok
    assert result.weight_coverage == 0.25
