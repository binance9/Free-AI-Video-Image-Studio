"""Light mesh optimizer for Character HD.

Pure NumPy + trimesh vertex clustering.  It intentionally keeps roughly 70%
of triangles so chibi/game details survive while GLB size and viewer cost fall.
Runs before optional Hunyuan3D-Paint, so texture UVs are not destroyed.
"""
from __future__ import annotations

import numpy as np
import trimesh


def _cluster_once(mesh: trimesh.Trimesh, cell_ratio: float) -> trimesh.Trimesh:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(vertices) == 0 or len(faces) == 0:
        return mesh.copy()

    max_extent = float(np.ptp(vertices, axis=0).max())
    if not np.isfinite(max_extent) or max_extent <= 1e-9:
        return mesh.copy()
    cell = max(max_extent * float(cell_ratio), 1e-7)

    origin = vertices.min(axis=0)
    keys = np.floor((vertices - origin) / cell).astype(np.int32)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(inverse)

    new_vertices = np.column_stack([
        np.bincount(inverse, weights=vertices[:, axis]) / counts
        for axis in range(3)
    ])
    new_faces = inverse[faces]
    keep = (
        (new_faces[:, 0] != new_faces[:, 1]) &
        (new_faces[:, 1] != new_faces[:, 2]) &
        (new_faces[:, 2] != new_faces[:, 0])
    )
    new_faces = new_faces[keep]

    if len(new_faces):
        # Remove duplicate triangles while preserving the orientation of the
        # first occurrence.
        face_keys = np.sort(new_faces, axis=1)
        _, first = np.unique(face_keys, axis=0, return_index=True)
        new_faces = new_faces[np.sort(first)]

    out = trimesh.Trimesh(vertices=new_vertices, faces=new_faces, process=False)
    out.remove_unreferenced_vertices()
    try:
        out.fix_normals()
    except Exception:
        pass
    return out


def optimize_mesh_light(mesh: trimesh.Trimesh, *, min_faces: int = 250_000) -> tuple[trimesh.Trimesh, dict]:
    """Reduce a dense Character HD mesh gently, usually to ~65-75% faces."""
    original_faces = int(len(mesh.faces))
    original_vertices = int(len(mesh.vertices))
    if original_faces <= int(min_faces):
        return mesh, {
            "optimized": False,
            "faces_before": original_faces,
            "faces_after": original_faces,
            "vertices_before": original_vertices,
            "vertices_after": original_vertices,
            "keep_ratio": 1.0,
        }

    # Hunyuan meshes are normalized; 0.2% of the largest extent gave a mild
    # reduction on dense character/weapon meshes without visibly changing form.
    out = _cluster_once(mesh, 0.0020)
    ratio = len(out.faces) / max(1, original_faces)

    # One corrective retry only; keeps runtime predictable and avoids an
    # expensive multi-pass decimator on ~1M triangle meshes.
    if ratio > 0.82:
        candidate = _cluster_once(mesh, 0.0025)
        if len(candidate.faces) < len(out.faces):
            out = candidate
            ratio = len(out.faces) / max(1, original_faces)
    elif ratio < 0.58:
        candidate = _cluster_once(mesh, 0.0015)
        if len(candidate.faces) > len(out.faces):
            out = candidate
            ratio = len(out.faces) / max(1, original_faces)

    return out, {
        "optimized": True,
        "faces_before": original_faces,
        "faces_after": int(len(out.faces)),
        "vertices_before": original_vertices,
        "vertices_after": int(len(out.vertices)),
        "keep_ratio": float(ratio),
    }
