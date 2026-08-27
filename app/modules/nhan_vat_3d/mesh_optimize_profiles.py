"""Character HD mesh optimization profiles.

Keeps the existing gentle HD optimizer as the recommended default, and adds
stronger optional profiles for game export.  All profiles use the same local
NumPy/trimesh vertex-clustering backend so no extra package is required.
"""
from __future__ import annotations

import trimesh

try:
    from .mesh_optimize_light import _cluster_once, optimize_mesh_light
except ImportError:  # direct runner execution inside the isolated Character HD venv
    from mesh_optimize_light import _cluster_once, optimize_mesh_light


PROFILES = {
    "hd": {
        "label": "HD",
        "target": "~65-75% tam giác",
        "cell_ratio": 0.0020,
        "min_faces": 250_000,
    },
    "medium": {
        "label": "Medium",
        "target": "~25-35% tam giác",
        "cell_ratio": 0.0042,
        "min_faces": 280_000,
    },
    "light": {
        "label": "Light",
        "target": "~10-18% tam giác",
        "cell_ratio": 0.0065,
        "min_faces": 150_000,
    },
}


def normalize_profile(profile: str | None) -> str:
    value = str(profile or "hd").strip().lower()
    return value if value in PROFILES else "hd"


def optimize_mesh_profile(mesh: trimesh.Trimesh, profile: str = "hd") -> tuple[trimesh.Trimesh, dict]:
    """Optimize a Character HD mesh using a named quality profile.

    hd      -> the already-tested gentle optimizer (~65-75% on dense Hunyuan meshes)
    medium  -> game-oriented reduction (~25-35%)
    light   -> aggressive game-light reduction (~10-18%)
    """
    profile = normalize_profile(profile)
    cfg = PROFILES[profile]
    original_faces = int(len(mesh.faces))
    original_vertices = int(len(mesh.vertices))

    if profile == "hd":
        out, stats = optimize_mesh_light(mesh, min_faces=int(cfg["min_faces"]))
        stats = dict(stats)
    elif original_faces <= int(cfg["min_faces"]):
        out = mesh
        stats = {
            "optimized": False,
            "faces_before": original_faces,
            "faces_after": original_faces,
            "vertices_before": original_vertices,
            "vertices_after": original_vertices,
            "keep_ratio": 1.0,
        }
    else:
        out = _cluster_once(mesh, float(cfg["cell_ratio"]))
        ratio = len(out.faces) / max(1, original_faces)

        # One gentle corrective retry if a mesh lands far outside the intended
        # range.  Hunyuan meshes are normalized, so these ratios stay stable
        # while keeping runtime predictable even around one million triangles.
        if profile == "medium":
            if ratio > 0.38:
                candidate = _cluster_once(mesh, 0.0048)
                if len(candidate.faces) < len(out.faces):
                    out = candidate
                    ratio = len(out.faces) / max(1, original_faces)
            elif ratio < 0.22:
                candidate = _cluster_once(mesh, 0.0037)
                if len(candidate.faces) > len(out.faces):
                    out = candidate
                    ratio = len(out.faces) / max(1, original_faces)
        elif profile == "light":
            if ratio > 0.20:
                candidate = _cluster_once(mesh, 0.0075)
                if len(candidate.faces) < len(out.faces):
                    out = candidate
                    ratio = len(out.faces) / max(1, original_faces)
            elif ratio < 0.09:
                candidate = _cluster_once(mesh, 0.0058)
                if len(candidate.faces) > len(out.faces):
                    out = candidate
                    ratio = len(out.faces) / max(1, original_faces)

        stats = {
            "optimized": int(len(out.faces)) < original_faces,
            "faces_before": original_faces,
            "faces_after": int(len(out.faces)),
            "vertices_before": original_vertices,
            "vertices_after": int(len(out.vertices)),
            "keep_ratio": float(ratio),
        }

    stats["profile"] = profile
    stats["profile_label"] = str(cfg["label"])
    stats["target"] = str(cfg["target"])
    return out, stats
