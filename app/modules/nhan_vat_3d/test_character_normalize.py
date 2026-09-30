"""Direct tests; run with the isolated runtime that owns trimesh."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from character_normalize import normalize_character_glb
from character_qa_render import VIEWS, render_qa_views


def run() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        # Deliberately Z-up, off-center and below ground.
        body = trimesh.creation.capsule(radius=0.28, height=1.25)
        body.apply_translation([0.35, -0.2, 0.5])
        scene = trimesh.Scene(body)
        src, dst = root / "source.glb", root / "normalized.glb"
        scene.export(src)
        report = normalize_character_glb(src, dst)
        assert report["geometry_pass"]
        assert report["orientation"] == "Y-up"
        assert abs(report["height_m"] - 1.8) < 1e-5
        assert report["ground_pass"]
        assert report["pivot_center_pass"]
        assert report["export_roundtrip_pass"]
        assert np.isfinite(np.asarray(report["bounds"])).all()
        assert report["skeleton_present"] is False
        renders = render_qa_views(dst, root / "qa_renders", size=192)
        assert tuple(renders["views"]) == VIEWS
        assert all(Path(path).is_file() for path in renders["views"].values())
        print("AIVF_CHARACTER_NORMALIZE_TESTS|PASS", report)

        # Semantic meshes exercise the conditional checks. Current generated
        # Hunyuan/TripoSR assets are merged, so these checks correctly report
        # unsupported there instead of manufacturing eye/mouth PASS results.
        semantic = trimesh.Scene()
        body = trimesh.creation.box([0.55, 1.55, 0.28])
        body.apply_translation([0, 0.775, 0])
        head = trimesh.creation.icosphere(subdivisions=2, radius=0.12)
        head.apply_translation([0, 1.68, 0])
        eye_l = trimesh.creation.icosphere(subdivisions=1, radius=0.025)
        eye_l.apply_translation([-0.045, 1.70, 0.105])
        eye_r = eye_l.copy()
        eye_r.apply_translation([0.09, 0, 0])
        mouth = trimesh.creation.box([0.07, 0.015, 0.01])
        mouth.apply_translation([0, 1.62, 0.12])
        garment = trimesh.Trimesh(
            vertices=[[-0.1, 0.7, 0.145], [0.1, 0.7, 0.145], [0.0, 0.9, 0.145]],
            faces=[[0, 1, 2]], process=False,
        )
        garment.visual = trimesh.visual.texture.TextureVisuals(
            uv=np.asarray([[0, 0], [1, 0], [0.5, 1]], dtype=float),
            material=trimesh.visual.material.PBRMaterial(
                baseColorTexture=Image.new("RGBA", (4, 4), (180, 80, 40, 255)),
                metallicFactor=0.0, roughnessFactor=0.8,
            ),
        )
        for name, mesh in (("body", body), ("head", head), ("eye.L", eye_l),
                           ("eye.R", eye_r), ("mouth", mouth), ("garment", garment)):
            semantic.add_geometry(mesh, geom_name=name, node_name=name)
        semantic_src, semantic_dst = root / "semantic.glb", root / "semantic_normalized.glb"
        semantic.export(semantic_src)
        semantic_report = normalize_character_glb(semantic_src, semantic_dst)
        assert semantic_report["eye_count"] == 2
        assert semantic_report["eye_symmetry_pass"] is True
        assert semantic_report["mouth_centered_pass"] is True
        assert semantic_report["head_to_body_ratio_pass"] is True
        assert semantic_report["textures"] >= 1 and semantic_report["images"] >= 1
        assert semantic_report["material_roundtrip_pass"]
        assert semantic_report["ready_for_rig"] is False  # gaze/lip landmarks remain unavailable
        print("AIVF_CHARACTER_SEMANTIC_TESTS|PASS", semantic_report)


if __name__ == "__main__":
    run()
