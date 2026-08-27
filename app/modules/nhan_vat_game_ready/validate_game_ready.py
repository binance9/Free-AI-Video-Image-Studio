"""Validate that a Game Ready GLB actually has a working rig + skin +
animations - thuan stdlib (struct + json), khong can trimesh/Blender. Doc
truc tiep GLB binary + JSON chunk theo dung glTF 2.0 spec, cung phong cach
voi app/modules/do_vat_3d/kiem_tra_do_vat.py nhung sau hon: phai kiem tra
duoc ca skin/joint/weight THAT va keyframe THAT, khong chi doc ten field.

Ly do module nay ton tai: Blender's bpy.ops.object.parent_set(type=
"ARMATURE_AUTO") KHONG rai exception khi bone-heat solve that bai mot phan -
no chi in warning va de lai vertex group gan nhu rong. glTF exporter cua
Blender sau do tu am lang bo skin ("has no skin, skipping") khi khong tim
duoc weight nao dung duoc. Neu chi tin "job Python khong loi" thi se bao
PASS gia cho 1 GLB thuc te khong the animate - day la validator doc lap de
phat hien dung truong hop do.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_CLIPS = ("idle", "run", "attack_01")
MIN_WEIGHT_COVERAGE = 0.85
MOTION_EPSILON = 1e-4

# ---- run-cycle gait numeric thresholds (see _validate_run_gait) ----
# Calibrated with real margin below what a real Blender export actually
# produces (verified: thigh range ~63deg / ~1.1rad, knee range ~49deg /
# ~0.85rad, hips vertical range ~0.02, L/R correlation exactly -1.0) - these
# are deliberately loose enough to tolerate a different but still-genuine
# gait, while still catching "barely moving" or "both legs in phase".
MIN_LEG_ROTATION_RANGE = 0.35   # rad (~20deg) peak-to-peak swing per thigh
MIN_KNEE_BEND_RANGE = 0.25      # rad (~14deg) peak-to-peak knee bend per leg
MIN_HIPS_VERTICAL_RANGE = 0.005 # hips translation, largest-axis peak-to-peak
MAX_LEG_PHASE_CORRELATION = -0.5  # Pearson r between L/R thigh angle over time; must be this negative or lower

# (struct format char, byte size)
_COMPONENT = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
    5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4),
}
_TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_NORMALIZED_INT_MAX = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


class GlbKhongHopLe(ValueError):
    pass


@dataclass
class KetQuaKiemTraGameReady:
    ok: bool = False
    animation_ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mesh_count: int = 0
    vertex_count: int = 0
    triangle_count: int = 0
    skins_count: int = 0
    joints_count: int = 0
    has_joints_attr: bool = False
    has_weights_attr: bool = False
    weight_coverage: float = 0.0
    animations: list[str] = field(default_factory=list)
    clip_keyframes: dict = field(default_factory=dict)
    clip_has_motion: dict = field(default_factory=dict)
    required_clips_present: dict = field(default_factory=dict)
    required_clips_animated: dict = field(default_factory=dict)
    run_gait: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "animation_ok": self.animation_ok,
            "errors": self.errors, "warnings": self.warnings,
            "mesh_count": self.mesh_count, "vertex_count": self.vertex_count,
            "triangle_count": self.triangle_count, "skins_count": self.skins_count,
            "joints_count": self.joints_count, "has_joints_attr": self.has_joints_attr,
            "has_weights_attr": self.has_weights_attr, "weight_coverage": round(self.weight_coverage, 4),
            "animations": self.animations, "clip_keyframes": self.clip_keyframes,
            "clip_has_motion": self.clip_has_motion,
            "required_clips_present": self.required_clips_present,
            "required_clips_animated": self.required_clips_animated,
            "run_gait": self.run_gait,
        }


def _read_glb_chunks(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise GlbKhongHopLe("File quá nhỏ, không đủ header GLB")
    magic, version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise GlbKhongHopLe("File không đúng định dạng GLB (thiếu magic 'glTF')")
    offset = 12
    json_chunk = None
    bin_chunk = None
    while offset < len(data):
        if offset + 8 > len(data):
            break
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        start = offset + 8
        end = start + chunk_length
        if end > len(data):
            break
        payload = data[start:end]
        if chunk_type == b"JSON":
            json_chunk = payload
        elif chunk_type == b"BIN\x00":
            bin_chunk = payload
        offset = end
    if json_chunk is None:
        raise GlbKhongHopLe("File GLB không có JSON chunk hợp lệ")
    try:
        doc = json.loads(json_chunk.decode("utf-8"))
    except Exception as exc:
        raise GlbKhongHopLe(f"JSON chunk trong GLB không đọc được: {exc}") from exc
    return doc, bin_chunk or b""


def _read_accessor_raw(doc: dict, bin_data: bytes, index: int) -> list[tuple]:
    """Generic accessor reader: returns 1 tuple of raw (un-normalized) numbers per element."""
    accessors = doc.get("accessors") or []
    if index is None or index >= len(accessors):
        raise GlbKhongHopLe(f"Accessor index {index} không tồn tại")
    acc = accessors[index]
    if acc.get("bufferView") is None:
        return [(0,) * _TYPE_N.get(acc.get("type"), 1)] * int(acc.get("count", 0))
    view = (doc.get("bufferViews") or [])[acc["bufferView"]]
    comp = _COMPONENT.get(acc.get("componentType"))
    n = _TYPE_N.get(acc.get("type"))
    if not comp or not n:
        raise GlbKhongHopLe("Kiểu accessor GLB chưa hỗ trợ")
    comp_code, comp_size = comp
    stride = view.get("byteStride") or comp_size * n
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    fmt = "<" + comp_code * n
    out = []
    for i in range(int(acc.get("count", 0))):
        row = base + i * stride
        out.append(struct.unpack_from(fmt, bin_data, row))
    return out


def _read_accessor_normalized(doc: dict, bin_data: bytes, index: int) -> list[tuple]:
    """Like _read_accessor_raw but applies glTF normalization (0..1 / -1..1)
    for integer component types - needed for WEIGHTS_0."""
    accessors = doc.get("accessors") or []
    acc = accessors[index]
    comp_type = acc.get("componentType")
    raw = _read_accessor_raw(doc, bin_data, index)
    if comp_type == 5126:  # FLOAT already normalized-by-value
        return raw
    max_val = _NORMALIZED_INT_MAX.get(comp_type)
    if not max_val:
        return raw
    if comp_type in (5120, 5122):  # signed -> [-1, 1]
        return [tuple(max(v / max_val, -1.0) for v in row) for row in raw]
    return [tuple(v / max_val for v in row) for row in raw]  # unsigned -> [0, 1]


def _channel_has_motion(values: list[tuple]) -> bool:
    if len(values) < 2:
        return False
    first = values[0]
    for row in values[1:]:
        if any(abs(a - b) > MOTION_EPSILON for a, b in zip(first, row)):
            return True
    return False


def _node_name_index(doc: dict) -> dict:
    return {node.get("name"): i for i, node in enumerate(doc.get("nodes") or []) if node.get("name")}


def _clip_channel(doc: dict, bin_data: bytes, anim: dict, node_index: int, path: str):
    """Return (times, values) for the FIRST channel of `anim` targeting
    `node_index` on `path`, sorted by time. None if not found/unreadable."""
    samplers = anim.get("samplers") or []
    for ch in anim.get("channels") or []:
        target = ch.get("target") or {}
        if target.get("node") != node_index or target.get("path") != path:
            continue
        sampler_idx = ch.get("sampler")
        if sampler_idx is None or sampler_idx >= len(samplers):
            continue
        sampler = samplers[sampler_idx]
        try:
            times = [t[0] for t in _read_accessor_raw(doc, bin_data, sampler.get("input"))]
            values = _read_accessor_raw(doc, bin_data, sampler.get("output"))
        except GlbKhongHopLe:
            return None
        pairs = sorted(zip(times, values), key=lambda p: p[0])
        return [p[0] for p in pairs], [p[1] for p in pairs]
    return None


def _signed_angle_x(quat: tuple) -> float:
    """Signed rotation angle (radians) about local X, valid exactly when
    the quaternion represents a pure-X rotation (true here: every run-cycle
    channel this is used on was authored with rotation_euler=(x,0,0,0)).
    Includes whatever constant rest/bind offset the exporter baked in -
    that offset is irrelevant for range/correlation, which only look at
    how the value CHANGES across the clip."""
    x, _y, _z, w = quat
    return 2.0 * math.atan2(x, w)


def _unwrap(angles: list[float], discont: float = math.pi) -> list[float]:
    """Classic phase unwrap: keeps a sequence of angles continuous across
    the +-pi wrap boundary, assuming consecutive samples never actually
    jump by more than `discont` radians (true for a per-frame-baked clip)."""
    out = list(angles)
    for i in range(1, len(out)):
        d = out[i] - out[i - 1]
        while d > discont:
            out[i] -= 2 * math.pi
            d = out[i] - out[i - 1]
        while d < -discont:
            out[i] += 2 * math.pi
            d = out[i] - out[i - 1]
    return out


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def _bone_rotation_x_range(doc: dict, bin_data: bytes, anim: dict, node_index: int) -> float | None:
    channel = _clip_channel(doc, bin_data, anim, node_index, "rotation")
    if channel is None:
        return None
    _times, values = channel
    if len(values) < 2:
        return 0.0
    angles = _unwrap([_signed_angle_x(q) for q in values])
    return max(angles) - min(angles)


def _validate_run_gait(doc: dict, bin_data: bytes, run_anim: dict) -> dict:
    """Numeric motion checks for the 'run' clip specifically (section 13 of
    the run-cycle fix): NOT just "some channel changed", but the actual
    biomechanics the animation is supposed to show - legs swinging in real
    opposite phase, knees actually bending, hips moving vertically."""
    node_index = _node_name_index(doc)
    out = {
        "thigh_l_range": None, "thigh_r_range": None,
        "knee_l_range": None, "knee_r_range": None,
        "hips_vertical_range": None, "legs_anti_phase": None,
        "leg_phase_correlation": None, "ok": False, "issues": [],
    }

    required_bones = ("thigh.L", "thigh.R", "shin.L", "shin.R", "hips")
    missing = [b for b in required_bones if b not in node_index]
    if missing:
        out["issues"].append(f"Thiếu bone để kiểm tra gait: {', '.join(missing)}")
        return out

    thigh_l_ch = _clip_channel(doc, bin_data, run_anim, node_index["thigh.L"], "rotation")
    thigh_r_ch = _clip_channel(doc, bin_data, run_anim, node_index["thigh.R"], "rotation")
    if thigh_l_ch is None or thigh_r_ch is None or len(thigh_l_ch[1]) < 2 or len(thigh_r_ch[1]) < 2:
        out["issues"].append("Clip 'run' không có rotation channel thật cho thigh.L/thigh.R")
        return out

    angles_l = _unwrap([_signed_angle_x(q) for q in thigh_l_ch[1]])
    angles_r = _unwrap([_signed_angle_x(q) for q in thigh_r_ch[1]])
    out["thigh_l_range"] = round(max(angles_l) - min(angles_l), 4)
    out["thigh_r_range"] = round(max(angles_r) - min(angles_r), 4)

    n = min(len(angles_l), len(angles_r))
    correlation = _pearson(angles_l[:n], angles_r[:n])
    out["leg_phase_correlation"] = round(correlation, 4)
    out["legs_anti_phase"] = correlation <= MAX_LEG_PHASE_CORRELATION

    out["knee_l_range"] = round(_bone_rotation_x_range(doc, bin_data, run_anim, node_index["shin.L"]) or 0.0, 4)
    out["knee_r_range"] = round(_bone_rotation_x_range(doc, bin_data, run_anim, node_index["shin.R"]) or 0.0, 4)

    hips_ch = _clip_channel(doc, bin_data, run_anim, node_index["hips"], "translation")
    if hips_ch is not None and len(hips_ch[1]) >= 2:
        best = 0.0
        for axis in range(3):
            vals = [v[axis] for v in hips_ch[1]]
            best = max(best, max(vals) - min(vals))
        out["hips_vertical_range"] = round(best, 5)
    else:
        out["hips_vertical_range"] = 0.0

    if out["thigh_l_range"] < MIN_LEG_ROTATION_RANGE:
        out["issues"].append(f"thigh.L rotation range quá nhỏ ({out['thigh_l_range']:.3f} rad < {MIN_LEG_ROTATION_RANGE})")
    if out["thigh_r_range"] < MIN_LEG_ROTATION_RANGE:
        out["issues"].append(f"thigh.R rotation range quá nhỏ ({out['thigh_r_range']:.3f} rad < {MIN_LEG_ROTATION_RANGE})")
    if not out["legs_anti_phase"]:
        out["issues"].append(
            f"Hai chân KHÔNG ngược pha (correlation={out['leg_phase_correlation']:.2f}, "
            f"cần <= {MAX_LEG_PHASE_CORRELATION}) - có thể đang chạy cùng pha (2 chân cùng đưa ra một lúc)"
        )
    if out["knee_l_range"] < MIN_KNEE_BEND_RANGE:
        out["issues"].append(f"shin.L (gối) không bend đủ ({out['knee_l_range']:.3f} rad < {MIN_KNEE_BEND_RANGE})")
    if out["knee_r_range"] < MIN_KNEE_BEND_RANGE:
        out["issues"].append(f"shin.R (gối) không bend đủ ({out['knee_r_range']:.3f} rad < {MIN_KNEE_BEND_RANGE})")
    if out["hips_vertical_range"] < MIN_HIPS_VERTICAL_RANGE:
        out["issues"].append(f"hips không có chuyển động lên/xuống đủ ({out['hips_vertical_range']:.4f} < {MIN_HIPS_VERTICAL_RANGE})")

    out["ok"] = len(out["issues"]) == 0
    return out


def validate_game_ready_glb(path: str | Path) -> KetQuaKiemTraGameReady:
    path = Path(path)
    result = KetQuaKiemTraGameReady()
    if not path.exists():
        result.errors.append("File game_ready.glb không tồn tại")
        return result

    try:
        doc, bin_data = _read_glb_chunks(path)
    except GlbKhongHopLe as exc:
        result.errors.append(str(exc))
        return result

    # ---- mesh / scene basics ----
    scenes = doc.get("scenes") or []
    nodes = doc.get("nodes") or []
    meshes = doc.get("meshes") or []
    result.mesh_count = len(meshes)
    if not scenes:
        result.errors.append("GLB không có scene nào")
    if not nodes:
        result.errors.append("GLB không có node nào")
    if not meshes:
        result.errors.append("GLB không có mesh nào")

    vertex_count = 0
    triangle_count = 0
    for mesh in meshes:
        for prim in mesh.get("primitives") or []:
            attrs = prim.get("attributes") or {}
            pos_idx = attrs.get("POSITION")
            if pos_idx is not None:
                vertex_count += int((doc.get("accessors") or [])[pos_idx].get("count", 0))
            idx_idx = prim.get("indices")
            if idx_idx is not None:
                triangle_count += int((doc.get("accessors") or [])[idx_idx].get("count", 0)) // 3
            if attrs.get("JOINTS_0") is not None:
                result.has_joints_attr = True
            if attrs.get("WEIGHTS_0") is not None:
                result.has_weights_attr = True
    result.vertex_count = vertex_count
    result.triangle_count = triangle_count

    if not result.has_joints_attr:
        result.errors.append("Mesh không có thuộc tính JOINTS_0")
    if not result.has_weights_attr:
        result.errors.append("Mesh không có thuộc tính WEIGHTS_0")

    # ---- skin ----
    skins = doc.get("skins") or []
    result.skins_count = len(skins)
    if not skins:
        result.errors.append("GLB không có skin nào (mesh không thực sự bind vào skeleton)")
    else:
        result.joints_count = sum(len(s.get("joints") or []) for s in skins)
        if result.joints_count == 0:
            result.errors.append("Skin tồn tại nhưng danh sách joints rỗng")
        for skin in skins:
            ibm_idx = skin.get("inverseBindMatrices")
            if ibm_idx is not None:
                try:
                    ibm = _read_accessor_raw(doc, bin_data, ibm_idx)
                    if len(ibm) != len(skin.get("joints") or []):
                        result.warnings.append("Số inverseBindMatrices không khớp số joints")
                except GlbKhongHopLe as exc:
                    result.warnings.append(f"inverseBindMatrices không đọc được: {exc}")

    # ---- weight coverage: the actual check that catches a silently-failed skin ----
    if result.has_weights_attr:
        total_verts = 0
        weighted_verts = 0
        for mesh in meshes:
            for prim in mesh.get("primitives") or []:
                w_idx = (prim.get("attributes") or {}).get("WEIGHTS_0")
                if w_idx is None:
                    continue
                try:
                    weights = _read_accessor_normalized(doc, bin_data, w_idx)
                except GlbKhongHopLe as exc:
                    result.warnings.append(f"WEIGHTS_0 không đọc được: {exc}")
                    continue
                total_verts += len(weights)
                weighted_verts += sum(1 for row in weights if sum(row) > 0.01)
        result.weight_coverage = (weighted_verts / total_verts) if total_verts else 0.0
        if total_verts and result.weight_coverage < MIN_WEIGHT_COVERAGE:
            result.errors.append(
                f"WEIGHTS_0 gần như toàn 0 (chỉ {result.weight_coverage:.0%} vertex có influence) - "
                "skin không dùng được dù có JOINTS_0/WEIGHTS_0"
            )

    # ---- animations ----
    animations = doc.get("animations") or []
    result.animations = [a.get("name") or f"clip_{i+1}" for i, a in enumerate(animations)]
    if len(animations) < len(REQUIRED_CLIPS):
        result.warnings.append(f"Chỉ có {len(animations)} animation, cần tối thiểu {len(REQUIRED_CLIPS)}")

    name_lookup = {}
    for i, anim in enumerate(animations):
        name = anim.get("name") or f"clip_{i+1}"
        max_keyframes = 0
        has_motion = False
        for ch in anim.get("channels") or []:
            sampler_idx = ch.get("sampler")
            samplers = anim.get("samplers") or []
            if sampler_idx is None or sampler_idx >= len(samplers):
                continue
            sampler = samplers[sampler_idx]
            try:
                times = _read_accessor_raw(doc, bin_data, sampler.get("input"))
                values = _read_accessor_raw(doc, bin_data, sampler.get("output"))
            except GlbKhongHopLe:
                continue
            max_keyframes = max(max_keyframes, len(times))
            if _channel_has_motion(values):
                has_motion = True
        result.clip_keyframes[name] = max_keyframes
        result.clip_has_motion[name] = has_motion
        name_lookup[name.strip().lower()] = name

    for required in REQUIRED_CLIPS:
        present_name = name_lookup.get(required.lower())
        result.required_clips_present[required] = present_name is not None
        if present_name is None:
            result.required_clips_animated[required] = False
            result.warnings.append(f"Thiếu animation clip bắt buộc: '{required}'")
            continue
        animated = bool(result.clip_has_motion.get(present_name))
        if not animated:
            result.required_clips_animated[required] = False
            result.warnings.append(
                f"Clip '{present_name}' tồn tại nhưng không có bone transform nào thay đổi thật "
                "(đứng yên) - không được tính là animation hợp lệ"
            )
            continue
        if required == "run":
            # "run" is held to a higher bar than "has some motion": it must
            # look like an actual alternating gait, not a bounce/twitch.
            run_anim = next(a for i, a in enumerate(animations) if (a.get("name") or f"clip_{i+1}") == present_name)
            gait = _validate_run_gait(doc, bin_data, run_anim)
            result.run_gait = gait
            result.required_clips_animated[required] = gait["ok"]
            for issue in gait["issues"]:
                result.warnings.append(f"run gait: {issue}")
        else:
            result.required_clips_animated[required] = True

    result.animation_ok = all(result.required_clips_animated.get(c) for c in REQUIRED_CLIPS)
    result.ok = len(result.errors) == 0
    return result
