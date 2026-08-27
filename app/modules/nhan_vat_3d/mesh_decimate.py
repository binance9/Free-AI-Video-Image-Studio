"""Decimate a GLB mesh toward a target triangle count.

Generic, no nhan_vat/do_vat specific logic - reuses the same NumPy+trimesh
vertex-clustering backend as mesh_optimize_light.py/mesh_optimize_profiles.py
(no new heavy dependency such as pymeshlab/open3d/fast_simplification, none
of which are installed in the isolated Character HD venv this script runs
under). Runs as a subprocess via the Character HD python (same pattern as
mesh_finish.py) because trimesh is not available in the main app venv.

Vertex clustering does not remap UV/material data, so this script is meant
to run on an UNTEXTURED shape mesh (do_vat_3d optimizes shape.glb BEFORE
texturing, not after - see dich_vu_do_vat_3d.py).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import trimesh

try:
    from .mesh_optimize_light import _cluster_once
except ImportError:  # direct runner execution inside the isolated venv
    from mesh_optimize_light import _cluster_once

MIN_CELL_RATIO = 0.0003
MAX_CELL_RATIO = 0.08
MAX_ITERATIONS = 10


def _as_mesh(scene_or_mesh) -> trimesh.Trimesh:
    if isinstance(scene_or_mesh, trimesh.Trimesh):
        return scene_or_mesh
    if isinstance(scene_or_mesh, trimesh.Scene):
        geometries = [g.copy() for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geometries:
            raise RuntimeError("GLB không có geometry hợp lệ")
        return trimesh.util.concatenate(geometries)
    raise RuntimeError("Định dạng mesh không hỗ trợ")


def decimate_to_target(mesh: trimesh.Trimesh, target_triangles: int, *, tolerance: float = 0.15) -> tuple[trimesh.Trimesh, dict]:
    """Iteratively search cell_ratio until face count lands within
    target*(1±tolerance), or give up after MAX_ITERATIONS and keep the
    closest candidate found. Never raises - worst case returns the mesh
    unchanged with optimized=False."""
    original_faces = int(len(mesh.faces))
    lo_bound = original_faces * (1.0 - tolerance)
    hi_bound = original_faces * (1.0 + tolerance)
    if target_triangles <= 0 or lo_bound <= target_triangles:
        return mesh, {"optimized": False, "iterations": 0, "faces_before": original_faces, "faces_after": original_faces}

    lo_ratio, hi_ratio = MIN_CELL_RATIO, MAX_CELL_RATIO
    best_mesh, best_faces, best_diff = mesh, original_faces, abs(original_faces - target_triangles)
    tol_lo = target_triangles * (1.0 - tolerance)
    tol_hi = target_triangles * (1.0 + tolerance)

    for i in range(MAX_ITERATIONS):
        ratio = (lo_ratio + hi_ratio) / 2.0
        candidate = _cluster_once(mesh, ratio)
        faces = int(len(candidate.faces))
        diff = abs(faces - target_triangles)
        if faces > 0 and diff < best_diff:
            best_mesh, best_faces, best_diff = candidate, faces, diff
        if tol_lo <= faces <= tol_hi and faces > 0:
            return candidate, {
                "optimized": True, "iterations": i + 1,
                "faces_before": original_faces, "faces_after": faces,
            }
        if faces == 0 or faces > target_triangles:
            # too few clusters merged (mesh still too dense) -> merge more aggressively
            lo_ratio = ratio
        else:
            # over-decimated -> back off
            hi_ratio = ratio

    return best_mesh, {
        "optimized": best_faces < original_faces,
        "iterations": MAX_ITERATIONS,
        "faces_before": original_faces,
        "faces_after": best_faces,
        "note": "Không hội tụ đúng tolerance sau số vòng lặp tối đa, dùng kết quả gần nhất",
    }


def run(src_path: str | Path, dst_path: str | Path, target_triangles: int, *, tolerance: float = 0.15) -> dict:
    src = Path(src_path).resolve()
    dst = Path(dst_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    loaded = trimesh.load(src, force="mesh", process=False, maintain_order=True)
    mesh = _as_mesh(loaded)
    original_faces = int(len(mesh.faces))
    original_vertices = int(len(mesh.vertices))

    out, stats = decimate_to_target(mesh, int(target_triangles), tolerance=float(tolerance))

    dst.parent.mkdir(parents=True, exist_ok=True)
    out.export(dst, file_type="glb")

    result = {
        "optimized": bool(stats.get("optimized", False)),
        "original_triangle_count": original_faces,
        "original_vertex_count": original_vertices,
        "optimized_triangle_count": int(len(out.faces)),
        "optimized_vertex_count": int(len(out.vertices)),
        "poly_target": int(target_triangles),
        "tolerance": float(tolerance),
        "iterations": int(stats.get("iterations", 0)),
        "optimizer": "trimesh-vertex-clustering",
    }
    if "note" in stats:
        result["note"] = stats["note"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("target_triangles", type=int)
    parser.add_argument("--tolerance", type=float, default=0.15)
    args = parser.parse_args()
    result = run(args.src, args.dst, args.target_triangles, tolerance=args.tolerance)
    print("AIVF_MESH_DECIMATE_OK " + json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
