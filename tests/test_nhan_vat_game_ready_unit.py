"""Unit test cho nhan_vat_game_ready.validate_game_ready - KHONG can Blender,
tu dung GLB toi thieu bang struct+json (cung phong cach voi
tests/test_do_vat_3d_unit.py::_build_minimal_glb) de test validator doc lap.

Chay: pytest -q tests/test_nhan_vat_game_ready_unit.py
"""
from __future__ import annotations

import json
import math
import struct
import tempfile
from pathlib import Path

import pytest

from app.modules.nhan_vat_game_ready.validate_game_ready import (
    REQUIRED_CLIPS,
    _validate_run_gait,
    validate_game_ready_glb,
)

# ---------- generic minimal-GLB builder with optional skin + animations ----------


def _pack_floats(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _quat_x(angle: float) -> tuple:
    return (math.sin(angle / 2), 0.0, 0.0, math.cos(angle / 2))


def _run_gait_track(
    *, thigh_amp=0.55, knee_amp=0.85, hips_dip=0.02, in_phase=False,
) -> dict:
    """Reimplements (in pure Python, for tests only) the exact phase formula
    blender_game_ready.py::bake_run_cycle uses, so the fixture matches a real
    export. in_phase=True deliberately breaks it (thigh.R copies thigh.L
    instead of mirroring it) to exercise the anti-phase failure path."""
    times = [0.0, 0.25, 0.5, 0.75, 1.0]
    thigh_l, thigh_r, shin_l, shin_r, hips_z = [], [], [], [], []
    for t in times:
        phase_l = t % 1.0
        phase_r = phase_l if in_phase else (t + 0.5) % 1.0
        tl = thigh_amp * math.cos(2 * math.pi * phase_l)
        tr = thigh_amp * math.cos(2 * math.pi * phase_r)
        kl = -knee_amp * max(0.0, math.sin(2 * math.pi * (phase_l - 0.5)))
        kr = -knee_amp * max(0.0, math.sin(2 * math.pi * (phase_r - 0.5)))
        thigh_l.append(_quat_x(tl)); thigh_r.append(_quat_x(tr))
        shin_l.append(_quat_x(kl)); shin_r.append(_quat_x(kr))
        hips_z.append(-hips_dip if t in (0.25, 0.75) else 0.0)
    return {"times": times, "thigh.L": thigh_l, "thigh.R": thigh_r, "shin.L": shin_l, "shin.R": shin_r, "hips_z": hips_z}


def _build_game_ready_glb(
    path,
    *,
    with_skin: bool = True,
    with_joints_attr: bool = True,
    with_weights_attr: bool = True,
    weight_rows: list[list[float]] | None = None,
    clips: dict[str, str] | None = None,
    # clip name -> "motion" (2 differing keyframes), "static" (2 identical keyframes), or omit entirely
    run_gait: dict | None = None,
    # override for the "run" clip specifically when clips["run"]=="motion" - see _run_gait_track()
) -> None:
    """Build a tiny but structurally real glTF: 1 mesh (4 verts, 2 triangles),
    a 6-node skeleton (root -> hips -> thigh.L/R -> shin.L/R), a skin, and 0+
    animation clips. idle/attack_01 (and run when kind != "motion") get a
    single generic rotation channel on "hips"; run's "motion" case gets a
    real multi-bone anti-phase gait track (see _run_gait_track) so the
    run-specific numeric validation has real leg bones to check."""
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
        pad = (4 - len(data) % 4) % 4
        offset = len(buffers_bin)
        buffers_bin += data + b"\x00" * pad
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data)})
        return len(buffer_views) - 1

    def add_accessor(comp_type, count, type_, data_bytes, **extra):
        view = add_buffer_view(data_bytes)
        accessors.append({"bufferView": view, "componentType": comp_type, "count": count, "type": type_, **extra})
        return len(accessors) - 1

    # POSITION
    pos_acc = add_accessor(5126, 4, "VEC3", _pack_floats(positions), min=[0.0, 0.0, 0.0], max=[1.0, 1.0, 1.0])
    idx_acc = add_accessor(5123, len(indices), "SCALAR", struct.pack(f"<{len(indices)}H", *indices))

    attributes = {"POSITION": pos_acc}
    if with_joints_attr:
        joints_flat = [v for row in joints_rows for v in row]
        attributes["JOINTS_0"] = add_accessor(5123, 4, "VEC4", struct.pack(f"<{len(joints_flat)}H", *joints_flat))
    if with_weights_attr:
        weights_flat = [v for row in weight_rows for v in row]
        attributes["WEIGHTS_0"] = add_accessor(5126, 4, "VEC4", _pack_floats(weights_flat))

    # 0=root 1=hips 2=thigh.L 3=shin.L 4=thigh.R 5=shin.R 6=MeshNode
    nodes = [
        {"name": "root", "children": [1]},
        {"name": "hips", "children": [2, 4], "rotation": [0, 0, 0, 1]},
        {"name": "thigh.L", "children": [3], "rotation": [0, 0, 0, 1]},
        {"name": "shin.L", "rotation": [0, 0, 0, 1]},
        {"name": "thigh.R", "children": [5], "rotation": [0, 0, 0, 1]},
        {"name": "shin.R", "rotation": [0, 0, 0, 1]},
        {"name": "MeshNode", "mesh": 0, "skin": 0 if with_skin else None},
    ]
    if not with_skin:
        del nodes[6]["skin"]
    joint_nodes = [1, 2, 3, 4, 5]
    node_index = {n["name"]: i for i, n in enumerate(nodes)}

    doc = {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0, 6]}],
        "scene": 0,
        "nodes": nodes,
        "meshes": [{"primitives": [{"attributes": attributes, "indices": idx_acc}]}],
    }

    if with_skin:
        ibm_flat = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] * len(joint_nodes)
        ibm_acc = add_accessor(5126, len(joint_nodes), "MAT4", _pack_floats([float(v) for v in ibm_flat]))
        doc["skins"] = [{"joints": joint_nodes, "inverseBindMatrices": ibm_acc}]

    def rotation_channel(node_idx, times, quats):
        time_acc = add_accessor(5126, len(times), "SCALAR", _pack_floats(times))
        value_acc = add_accessor(5126, len(quats), "VEC4", _pack_floats([v for q in quats for v in q]))
        return {
            "sampler_input": time_acc, "sampler_output": value_acc,
            "channel": {"target": {"node": node_idx, "path": "rotation"}},
        }

    def translation_channel(node_idx, times, vecs):
        time_acc = add_accessor(5126, len(times), "SCALAR", _pack_floats(times))
        value_acc = add_accessor(5126, len(vecs), "VEC3", _pack_floats([v for vec in vecs for v in vec]))
        return {
            "sampler_input": time_acc, "sampler_output": value_acc,
            "channel": {"target": {"node": node_idx, "path": "translation"}},
        }

    def build_clip(name, parts):
        samplers, channels = [], []
        for part in parts:
            samplers.append({"input": part["sampler_input"], "output": part["sampler_output"], "interpolation": "LINEAR"})
            ch = dict(part["channel"]); ch["sampler"] = len(samplers) - 1
            channels.append(ch)
        return {"name": name, "samplers": samplers, "channels": channels}

    animations = []
    for name, kind in clips.items():
        if kind is None:
            continue
        if name.strip().lower() == "run" and kind == "motion":
            gait = run_gait if run_gait is not None else _run_gait_track()
            times = gait["times"]
            parts = [
                rotation_channel(node_index["thigh.L"], times, gait["thigh.L"]),
                rotation_channel(node_index["thigh.R"], times, gait["thigh.R"]),
                rotation_channel(node_index["shin.L"], times, gait["shin.L"]),
                rotation_channel(node_index["shin.R"], times, gait["shin.R"]),
                translation_channel(node_index["hips"], times, [(0.0, 0.0, z) for z in gait["hips_z"]]),
            ]
            animations.append(build_clip(name, parts))
            continue
        # generic clip (idle, attack_01, or run in its "static"/no-motion form): 1 channel on hips
        if kind == "motion":
            values = [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.7071, 0.7071)]
        else:  # "static"
            values = [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)]
        animations.append(build_clip(name, [rotation_channel(node_index["hips"], [0.0, 1.0], values)]))
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
    assert result.joints_count == 5
    assert result.has_joints_attr and result.has_weights_attr
    assert result.weight_coverage == 1.0
    assert set(result.animations) == {"idle", "run", "attack_01"}
    assert result.run_gait["ok"], result.run_gait["issues"]
    assert result.run_gait["legs_anti_phase"] is True


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


# ==================== run-cycle gait validation (section 13) ====================
# _validate_run_gait is exercised two ways: directly against a hand-built
# doc/bin (fast, no file I/O, precise control over each failure mode) and
# through the full validate_game_ready_glb(path) for the integration path.


def _run_doc_and_bin(gait: dict):
    """Minimal doc+bin containing ONLY what _validate_run_gait needs: named
    joint nodes and a 'run' animation with real accessors - no mesh/skin."""
    buffers_bin = b""
    buffer_views = []
    accessors = []

    def add_accessor(comp_type, count, type_, data_bytes):
        pad = (4 - len(data_bytes) % 4) % 4
        nonlocal buffers_bin
        offset = len(buffers_bin)
        buffers_bin += data_bytes + b"\x00" * pad
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data_bytes)})
        accessors.append({"bufferView": len(buffer_views) - 1, "componentType": comp_type, "count": count, "type": type_})
        return len(accessors) - 1

    nodes = [
        {"name": "root", "children": [1]}, {"name": "hips", "children": [2, 4]},
        {"name": "thigh.L", "children": [3]}, {"name": "shin.L"},
        {"name": "thigh.R", "children": [5]}, {"name": "shin.R"},
    ]
    node_index = {n["name"]: i for i, n in enumerate(nodes)}
    times = gait["times"]

    def rot_sampler(node_name, quats):
        t_acc = add_accessor(5126, len(times), "SCALAR", _pack_floats(times))
        v_acc = add_accessor(5126, len(quats), "VEC4", _pack_floats([v for q in quats for v in q]))
        return t_acc, v_acc, node_index[node_name]

    def trans_sampler(node_name, vecs):
        t_acc = add_accessor(5126, len(times), "SCALAR", _pack_floats(times))
        v_acc = add_accessor(5126, len(vecs), "VEC3", _pack_floats([v for vec in vecs for v in vec]))
        return t_acc, v_acc, node_index[node_name]

    samplers, channels = [], []

    def add_channel(t_acc, v_acc, node_idx, path):
        samplers.append({"input": t_acc, "output": v_acc})
        channels.append({"sampler": len(samplers) - 1, "target": {"node": node_idx, "path": path}})

    add_channel(*rot_sampler("thigh.L", gait["thigh.L"]), "rotation")
    add_channel(*rot_sampler("thigh.R", gait["thigh.R"]), "rotation")
    add_channel(*rot_sampler("shin.L", gait["shin.L"]), "rotation")
    add_channel(*rot_sampler("shin.R", gait["shin.R"]), "rotation")
    add_channel(*trans_sampler("hips", [(0.0, 0.0, z) for z in gait["hips_z"]]), "translation")

    doc = {"nodes": nodes, "accessors": accessors, "bufferViews": buffer_views}
    run_anim = {"name": "run", "samplers": samplers, "channels": channels}
    return doc, buffers_bin, run_anim


def test_run_gait_passes_with_real_anti_phase_cycle():
    doc, bin_data, run_anim = _run_doc_and_bin(_run_gait_track())
    gait = _validate_run_gait(doc, bin_data, run_anim)
    assert gait["ok"], gait["issues"]
    assert gait["legs_anti_phase"] is True
    assert gait["leg_phase_correlation"] <= -0.9
    assert gait["thigh_l_range"] > 0.9  # ~1.1 rad expected (2x amplitude)
    assert gait["knee_l_range"] > 0.7   # ~0.85 rad expected
    assert gait["hips_vertical_range"] >= 0.019


def test_run_gait_fails_when_legs_move_in_phase():
    """The exact bug this validator exists to catch: both thighs swinging
    together instead of alternating."""
    doc, bin_data, run_anim = _run_doc_and_bin(_run_gait_track(in_phase=True))
    gait = _validate_run_gait(doc, bin_data, run_anim)
    assert not gait["ok"]
    assert gait["legs_anti_phase"] is False
    assert gait["leg_phase_correlation"] > -0.5
    assert any("ngược pha" in issue for issue in gait["issues"])


def test_run_gait_fails_when_thigh_range_too_small():
    doc, bin_data, run_anim = _run_doc_and_bin(_run_gait_track(thigh_amp=0.05))
    gait = _validate_run_gait(doc, bin_data, run_anim)
    assert not gait["ok"]
    assert any("thigh" in issue.lower() for issue in gait["issues"])


def test_run_gait_fails_when_no_knee_bend():
    doc, bin_data, run_anim = _run_doc_and_bin(_run_gait_track(knee_amp=0.0))
    gait = _validate_run_gait(doc, bin_data, run_anim)
    assert not gait["ok"]
    assert any("gối" in issue.lower() or "shin" in issue.lower() for issue in gait["issues"])
    # anti-phase legs should still be fine even though knees don't bend
    assert gait["legs_anti_phase"] is True


def test_run_gait_fails_when_hips_do_not_move_vertically():
    doc, bin_data, run_anim = _run_doc_and_bin(_run_gait_track(hips_dip=0.0))
    gait = _validate_run_gait(doc, bin_data, run_anim)
    assert not gait["ok"]
    assert gait["hips_vertical_range"] == 0.0
    assert any("hips" in issue.lower() for issue in gait["issues"])


def test_run_gait_missing_leg_bones_reported_not_crashed():
    doc = {"nodes": [{"name": "root"}], "accessors": [], "bufferViews": []}
    run_anim = {"name": "run", "samplers": [], "channels": []}
    gait = _validate_run_gait(doc, b"", run_anim)
    assert not gait["ok"]
    assert "thigh.L" in gait["issues"][0]


def test_full_glb_run_clip_with_in_phase_legs_is_partial_not_pass(tmp_glb_path):
    _build_game_ready_glb(tmp_glb_path, run_gait=_run_gait_track(in_phase=True))
    result = validate_game_ready_glb(tmp_glb_path)
    assert result.ok  # mesh/skin still fine
    assert not result.animation_ok
    assert result.required_clips_animated["run"] is False
    assert result.run_gait["legs_anti_phase"] is False
