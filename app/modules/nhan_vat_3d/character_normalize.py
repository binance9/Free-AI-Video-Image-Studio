"""Normalize generated character GLBs without touching rigs or animation.

Executed by the backend-specific Python environment because the main app does
not own trimesh.  The normalizer deliberately refuses skinned/animated files:
Step 3 is pre-rig cleanup and must never rewrite an existing rig.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path

import numpy as np
import trimesh

TARGET_HEIGHT_METERS = 1.8
GROUND_TOLERANCE = 1e-5


def _glb_document(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise RuntimeError("File is not a binary glTF/GLB")
    json_len, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        raise RuntimeError("GLB has no JSON chunk")
    return json.loads(data[20:20 + json_len].decode("utf-8").rstrip("\x00 "))


def _capabilities(doc: dict) -> dict:
    names = [str(x.get("name") or "").lower() for x in doc.get("nodes", []) + doc.get("meshes", [])]
    eye_names = [name for name in names if "eye" in name or "eyeball" in name]
    mouth_names = [name for name in names if any(token in name for token in ("mouth", "lip", "jaw"))]
    face_names = [name for name in names if any(token in name for token in ("face", "head"))]
    return {
        "materials": len(doc.get("materials", [])),
        "textures": len(doc.get("textures", [])),
        "images": len(doc.get("images", [])),
        "skins": len(doc.get("skins", [])),
        "animations": len(doc.get("animations", [])),
        "morph_targets": sum(
            len(primitive.get("targets", []))
            for mesh in doc.get("meshes", [])
            for primitive in mesh.get("primitives", [])
        ),
        "face_mesh_named": bool(face_names),
        "eye_mesh_names": eye_names,
        "mouth_mesh_names": mouth_names,
    }


def _world_meshes(scene: trimesh.Scene) -> list[tuple[str, trimesh.Trimesh]]:
    result = []
    used: dict[str, int] = {}
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        source = scene.geometry.get(geometry_name)
        if not isinstance(source, trimesh.Trimesh):
            continue
        mesh = source.copy()
        mesh.apply_transform(transform)
        base = str(geometry_name or node_name or "mesh")
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f"{base}_{used[base]}"
        result.append((name, mesh))
    if not result:
        raise RuntimeError("GLB contains no triangle mesh")
    return result


def _combined(meshes: list[tuple[str, trimesh.Trimesh]]) -> trimesh.Trimesh:
    return trimesh.util.concatenate([mesh.copy() for _, mesh in meshes])


def _upright_matrix(extents: np.ndarray) -> tuple[np.ndarray, str]:
    matrix = np.eye(4)
    longest = int(np.argmax(extents))
    if longest == 0 and extents[0] > extents[1] * 1.15:
        matrix = trimesh.transformations.rotation_matrix(np.deg2rad(-90), [0, 0, 1])
        return matrix, "x-to-y"
    if longest == 2 and extents[2] > extents[1] * 1.15:
        matrix = trimesh.transformations.rotation_matrix(np.deg2rad(-90), [1, 0, 0])
        return matrix, "z-to-y"
    return matrix, "native-y"


def _symmetry_score(vertices: np.ndarray) -> float:
    if len(vertices) < 8:
        return 0.0
    x = vertices[:, 0]
    left = np.sort(np.abs(x[x < 0]))
    right = np.sort(x[x >= 0])
    count = min(len(left), len(right), 4096)
    if count < 4:
        return 0.0
    left_q = np.quantile(left, np.linspace(0, 1, count))
    right_q = np.quantile(right, np.linspace(0, 1, count))
    width = max(float(np.ptp(x)), 1e-9)
    return max(0.0, 1.0 - float(np.mean(np.abs(left_q - right_q))) / width)


def _semantic_checks(meshes: list[tuple[str, trimesh.Trimesh]], bounds: np.ndarray) -> dict:
    height = max(float(bounds[1, 1] - bounds[0, 1]), 1e-9)
    width = max(float(bounds[1, 0] - bounds[0, 0]), 1e-9)
    depth = max(float(bounds[1, 2] - bounds[0, 2]), 1e-9)
    eyes = [(name, mesh) for name, mesh in meshes if "eye" in name.lower() or "eyeball" in name.lower()]
    mouths = [(name, mesh) for name, mesh in meshes if any(x in name.lower() for x in ("mouth", "lip"))]
    heads = [(name, mesh) for name, mesh in meshes if any(x in name.lower() for x in ("head", "face"))]

    eye_symmetry = None
    if len(eyes) == 2:
        centers = [np.asarray(mesh.bounding_box.centroid, dtype=np.float64) for _, mesh in eyes]
        sizes = [np.asarray(mesh.extents, dtype=np.float64) for _, mesh in eyes]
        size_delta = float(np.max(np.abs(sizes[0] - sizes[1]) / np.maximum(np.maximum(sizes[0], sizes[1]), 1e-9)))
        eye_symmetry = bool(
            abs(float(centers[0][1] - centers[1][1])) <= height * 0.03
            and abs(float(centers[0][2] - centers[1][2])) <= depth * 0.05
            and abs(float(centers[0][0] + centers[1][0])) <= width * 0.08
            and centers[0][0] * centers[1][0] < 0
            and size_delta <= 0.20
        )

    mouth_centered = None
    if mouths:
        mouth_center = np.mean([mesh.bounding_box.centroid for _, mesh in mouths], axis=0)
        mouth_centered = bool(
            abs(float(mouth_center[0])) <= width * 0.10
            and bounds[0, 1] + height * 0.45 <= mouth_center[1] <= bounds[0, 1] + height * 0.95
        )

    head_ratio = None
    head_ratio_pass = None
    if heads:
        head_vertices = np.vstack([np.asarray(mesh.vertices) for _, mesh in heads])
        head_height = float(np.ptp(head_vertices[:, 1]))
        if head_height > 1e-9:
            head_ratio = height / head_height
            head_ratio_pass = 6.5 <= head_ratio <= 8.5

    return {
        "head_to_body_ratio": head_ratio,
        "head_to_body_ratio_pass": head_ratio_pass,
        "eye_count": len(eyes),
        "eye_symmetry_pass": eye_symmetry,
        # Iris/pupil direction and eyelid penetration need semantic landmarks;
        # named eyeball shells alone are not enough to claim a neutral gaze.
        "eye_forward_validation": "unsupported-without-iris-pupil-landmarks",
        "mouth_centered_pass": mouth_centered,
        "mouth_neutral_validation": "unsupported-without-lip-landmarks",
        "hair_face_intersection_validation": "unsupported-without-semantic-hair-mesh",
        "skin_material_validation": "unsupported-without-semantic-skin-material",
    }


def normalize_character_glb(src_path: str | Path, dst_path: str | Path) -> dict:
    src = Path(src_path).resolve()
    dst = Path(dst_path).resolve()
    before_doc = _glb_document(src)
    capability = _capabilities(before_doc)
    if capability["skins"] or capability["animations"]:
        raise RuntimeError("Refusing to normalize a skinned or animated GLB in pre-rig Step 3")

    scene = trimesh.load(src, force="scene", process=False, maintain_order=True)
    meshes = _world_meshes(scene)
    combined = _combined(meshes)
    vertices = np.asarray(combined.vertices, dtype=np.float64)
    faces = np.asarray(combined.faces, dtype=np.int64)
    if not len(vertices) or not len(faces):
        raise RuntimeError("Mesh has no vertices or triangle indices")
    if not np.isfinite(vertices).all() or not np.isfinite(faces).all():
        raise RuntimeError("Mesh contains NaN/Inf")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise RuntimeError("Mesh indices are out of range")

    orientation, orientation_mode = _upright_matrix(np.asarray(combined.extents, dtype=np.float64))
    for _, mesh in meshes:
        mesh.apply_transform(orientation)
    combined = _combined(meshes)
    bounds = np.asarray(combined.bounds, dtype=np.float64)
    height = float(bounds[1, 1] - bounds[0, 1])
    if not math.isfinite(height) or height <= 1e-8:
        raise RuntimeError("Character height is degenerate")
    scale = TARGET_HEIGHT_METERS / height
    global_transform = np.eye(4)
    global_transform[:3, :3] *= scale
    scaled_bounds = bounds * scale
    global_transform[:3, 3] = [
        -(scaled_bounds[0, 0] + scaled_bounds[1, 0]) / 2.0,
        -scaled_bounds[0, 1],
        -(scaled_bounds[0, 2] + scaled_bounds[1, 2]) / 2.0,
    ]

    output_scene = trimesh.Scene()
    duplicate_faces_removed = 0
    for name, mesh in meshes:
        mesh.apply_transform(global_transform)
        before_faces = len(mesh.faces)
        try:
            mesh.update_faces(mesh.unique_faces())
            mesh.remove_unreferenced_vertices()
        except Exception:
            pass
        duplicate_faces_removed += before_faces - len(mesh.faces)
        try:
            mesh.fix_normals(multibody=True)
        except Exception:
            pass
        output_scene.add_geometry(mesh, geom_name=name, node_name=name)

    dst.parent.mkdir(parents=True, exist_ok=True)
    output_scene.export(dst, file_type="glb")
    after_doc = _glb_document(dst)
    reloaded = trimesh.load(dst, force="scene", process=False, maintain_order=True)
    roundtrip_meshes = _world_meshes(reloaded)
    roundtrip = _combined(roundtrip_meshes)
    out_vertices = np.asarray(roundtrip.vertices, dtype=np.float64)
    out_faces = np.asarray(roundtrip.faces, dtype=np.int64)
    out_bounds = np.asarray(roundtrip.bounds, dtype=np.float64)
    out_extents = out_bounds[1] - out_bounds[0]
    after_capability = _capabilities(after_doc)
    semantic = _semantic_checks(roundtrip_meshes, out_bounds)

    geometry_pass = bool(
        len(out_vertices) and len(out_faces) and np.isfinite(out_vertices).all()
        and np.isfinite(out_faces).all() and out_faces.min() >= 0 and out_faces.max() < len(out_vertices)
        and np.isfinite(out_bounds).all() and np.all(out_extents > 1e-8)
    )
    ground_pass = abs(float(out_bounds[0, 1])) <= GROUND_TOLERANCE
    center_pass = abs(float((out_bounds[0, 0] + out_bounds[1, 0]) / 2.0)) <= GROUND_TOLERANCE and abs(
        float((out_bounds[0, 2] + out_bounds[1, 2]) / 2.0)
    ) <= GROUND_TOLERANCE
    turntable_center_drift = math.hypot(
        float((out_bounds[0, 0] + out_bounds[1, 0]) / 2.0),
        float((out_bounds[0, 2] + out_bounds[1, 2]) / 2.0),
    )
    body_width_ratio = float(out_extents[1] / max(out_extents[0], 1e-9))
    body_plausible = 1.35 <= body_width_ratio <= 5.0
    material_roundtrip = (
        after_capability["materials"] >= capability["materials"]
        and after_capability["textures"] >= capability["textures"]
        and after_capability["images"] >= capability["images"]
    )

    eye_system = "separate-eyeball-mesh" if len(capability["eye_mesh_names"]) >= 2 else "merged-surface-or-texture"
    mouth_system = "separate-mouth-mesh" if capability["mouth_mesh_names"] else "merged-surface-or-texture"
    report = {
        "geometry_pass": geometry_pass,
        "vertices": int(len(out_vertices)),
        "faces": int(len(out_faces)),
        "bounds": out_bounds.tolist(),
        "extents": out_extents.tolist(),
        "orientation": "Y-up",
        "orientation_mode": orientation_mode,
        "front_axis": "backend-native-preserved",
        "height_m": float(out_extents[1]),
        "scale_applied": float(scale),
        "ground_pass": ground_pass,
        "pivot_center_pass": center_pass,
        "turntable_center": [0.0, float(out_extents[1] / 2.0), 0.0],
        "turntable_center_drift": turntable_center_drift,
        "turntable_rotation_center_pass": turntable_center_drift <= GROUND_TOLERANCE,
        "body_width_ratio": body_width_ratio,
        "body_plausible": body_plausible,
        "symmetry_score": _symmetry_score(out_vertices),
        "duplicate_faces_removed": int(duplicate_faces_removed),
        "connected_components": int(len(roundtrip.split(only_watertight=False))),
        "materials": after_capability["materials"],
        "textures": after_capability["textures"],
        "images": after_capability["images"],
        "material_roundtrip_pass": material_roundtrip,
        "export_roundtrip_pass": geometry_pass and material_roundtrip,
        "face_system": "separate-head-mesh" if capability["face_mesh_named"] else "merged-surface",
        "eye_system": eye_system,
        "mouth_system": mouth_system,
        "eye_geometry_validation": "unsupported" if eye_system != "separate-eyeball-mesh" else "named-meshes-present",
        "mouth_geometry_validation": "unsupported" if mouth_system != "separate-mouth-mesh" else "named-mesh-present",
        "morph_targets": capability["morph_targets"],
        "skeleton_present": bool(capability["skins"]),
        "animations_present": bool(capability["animations"]),
        **semantic,
    }
    report["ready_for_rig"] = bool(
        report["geometry_pass"] and report["ground_pass"] and report["pivot_center_pass"]
        and report["turntable_rotation_center_pass"]
        and report["body_plausible"] and report["material_roundtrip_pass"]
        and report["export_roundtrip_pass"]
        and report["head_to_body_ratio_pass"] is True
        and report["eye_symmetry_pass"] is True
        and report["eye_forward_validation"] == "pass"
        and report["mouth_centered_pass"] is True
        and report["mouth_neutral_validation"] == "pass"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    args = parser.parse_args()
    report = normalize_character_glb(args.src, args.dst)
    print("AIVF_CHARACTER_NORMALIZED|" + json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
