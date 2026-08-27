"""Post-process GLB mesh for local viewer/export quality.

Goals:
- auto-orient standing characters/objects more naturally
- lightly smooth noisy surfaces
- center and ground the result for a cleaner viewer experience
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh


def _as_mesh(scene_or_mesh):
    if isinstance(scene_or_mesh, trimesh.Trimesh):
        return scene_or_mesh
    if isinstance(scene_or_mesh, trimesh.Scene):
        geometries = []
        for geom in scene_or_mesh.geometry.values():
            if isinstance(geom, trimesh.Trimesh):
                geometries.append(geom.copy())
        if not geometries:
            raise RuntimeError("GLB không có geometry hợp lệ")
        return trimesh.util.concatenate(geometries)
    raise RuntimeError("Định dạng mesh không hỗ trợ")


def _rotate_x(mesh: trimesh.Trimesh, degrees: float):
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(degrees), [1, 0, 0]))


def _rotate_z(mesh: trimesh.Trimesh, degrees: float):
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(degrees), [0, 0, 1]))


def auto_upright(mesh: trimesh.Trimesh) -> str:
    extents = mesh.extents
    mode = "native"
    if extents[0] > extents[1] * 1.2 and extents[0] > extents[2] * 1.05:
        _rotate_z(mesh, -90)
        mode = "auto-z-90"
    elif extents[2] > extents[1] * 1.2 and extents[2] > extents[0] * 1.05:
        _rotate_x(mesh, -90)
        mode = "auto-x-90"
    return mode


def center_and_ground(mesh: trimesh.Trimesh) -> None:
    bounds = mesh.bounds
    center_xz = np.array([(bounds[0, 0] + bounds[1, 0]) / 2.0, 0.0, (bounds[0, 2] + bounds[1, 2]) / 2.0])
    mesh.apply_translation(-center_xz)
    bounds = mesh.bounds
    mesh.apply_translation([0.0, -bounds[0, 1], 0.0])


def smooth_mesh(mesh: trimesh.Trimesh, iterations: int = 4) -> None:
    try:
        trimesh.smoothing.filter_taubin(mesh, lamb=0.35, nu=-0.37, iterations=iterations)
    except Exception:
        # Fallback to gentler Laplacian smoothing if Taubin is unavailable.
        trimesh.smoothing.filter_laplacian(mesh, lamb=0.28, iterations=max(1, iterations - 1))


def finish_glb(src_path: str | Path, dst_path: str | Path, *, smooth: bool = True) -> Path:
    src = Path(src_path).resolve()
    dst = Path(dst_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    loaded = trimesh.load(src, force="mesh", process=False, maintain_order=True)
    mesh = _as_mesh(loaded)
    auto_upright(mesh)
    if smooth and len(mesh.vertices) > 1000:
        smooth_mesh(mesh)
    center_and_ground(mesh)
    dst.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(dst, file_type="glb")
    return dst


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--no-smooth", action="store_true")
    args = parser.parse_args()
    out = finish_glb(args.src, args.dst, smooth=not args.no_smooth)
    print(f"AIVF_MESH_FINISH_OK {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
