"""Deterministic offscreen GLB renders for character visual QA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import moderngl
import numpy as np
import trimesh
from PIL import Image

VIEWS = ("front_full", "front_face", "left_three_quarter", "right_three_quarter", "side")

VERTEX_SHADER = """
#version 330
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_color;
out vec3 v_normal;
out vec2 v_uv;
out vec4 v_color;
void main() {
    gl_Position = vec4(in_position, 1.0);
    v_normal = in_normal;
    v_uv = in_uv;
    v_color = in_color;
}
"""

FRAGMENT_SHADER = """
#version 330
uniform sampler2D base_texture;
uniform bool use_texture;
in vec3 v_normal;
in vec2 v_uv;
in vec4 v_color;
out vec4 frag_color;
void main() {
    vec4 base = use_texture ? texture(base_texture, vec2(v_uv.x, 1.0-v_uv.y)) : v_color;
    vec3 n = normalize(v_normal);
    float key = max(dot(n, normalize(vec3(0.35, 0.75, 0.55))), 0.0);
    float fill = max(dot(n, normalize(vec3(-0.65, 0.25, 0.35))), 0.0);
    float light = 0.42 + 0.46 * key + 0.18 * fill;
    frag_color = vec4(base.rgb * light, base.a);
}
"""


def _world_meshes(path: Path) -> list[trimesh.Trimesh]:
    scene = trimesh.load(path, force="scene", process=False, maintain_order=True)
    result = []
    for node in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node]
        source = scene.geometry.get(geometry_name)
        if isinstance(source, trimesh.Trimesh):
            mesh = source.copy()
            mesh.apply_transform(transform)
            result.append(mesh)
    if not result:
        raise RuntimeError("GLB contains no renderable mesh")
    return result


def _camera(vertices: np.ndarray, view: str, width: int, height: int) -> dict:
    bounds = np.asarray([vertices.min(axis=0), vertices.max(axis=0)], dtype=np.float64)
    extents = bounds[1] - bounds[0]
    model_height = max(float(extents[1]), 1e-6)
    center = (bounds[0] + bounds[1]) / 2.0
    distance = max(float(np.linalg.norm(extents)), model_height) * 2.2
    target = np.asarray([center[0], bounds[0, 1] + model_height * 0.50, center[2]], dtype=np.float64)
    direction = {
        "front_full": np.asarray([0.0, 0.0, 1.0]),
        "front_face": np.asarray([0.0, 0.0, 1.0]),
        "left_three_quarter": np.asarray([0.70, 0.0, 0.70]),
        "right_three_quarter": np.asarray([-0.70, 0.0, 0.70]),
        "side": np.asarray([1.0, 0.0, 0.0]),
    }[view]
    direction /= np.linalg.norm(direction)
    if view == "front_face":
        target[1] = bounds[0, 1] + model_height * 0.78
        vertical_span = model_height * 0.50
    else:
        vertical_span = model_height * 1.10
    camera = target + direction * distance
    forward = (target - camera) / np.linalg.norm(target - camera)
    right = np.cross(forward, np.asarray([0.0, 1.0, 0.0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    aspect = width / height
    basis = np.vstack([right, up, -forward])
    return {"target": target, "camera": camera, "forward": forward, "right": right, "up": up,
            "basis": basis, "vertical_span": vertical_span, "aspect": aspect, "distance": distance}


def _project(vertices: np.ndarray, camera_data: dict) -> np.ndarray:
    relative = vertices - camera_data["target"]
    clip = np.column_stack([
        relative @ camera_data["right"] / (camera_data["vertical_span"] * camera_data["aspect"] / 2.0),
        relative @ camera_data["up"] / (camera_data["vertical_span"] / 2.0),
        ((vertices - camera_data["camera"]) @ camera_data["forward"] / (camera_data["distance"] * 2.0)) * 2.0 - 1.0,
    ]).astype("f4")
    return clip


def _rgba(mesh: trimesh.Trimesh) -> np.ndarray:
    colors = getattr(mesh.visual, "vertex_colors", None)
    if colors is not None and len(colors) == len(mesh.vertices):
        return np.asarray(colors, dtype=np.float32) / 255.0
    material = getattr(mesh.visual, "material", None)
    factor = getattr(material, "baseColorFactor", None)
    if factor is not None:
        value = np.asarray(factor, dtype=np.float32)
        if value.max() > 1.0:
            value /= 255.0
        return np.tile(value[:4], (len(mesh.vertices), 1))
    return np.tile(np.asarray([0.72, 0.72, 0.74, 1.0], dtype=np.float32), (len(mesh.vertices), 1))


def _texture(ctx, mesh: trimesh.Trimesh):
    material = getattr(mesh.visual, "material", None)
    image = getattr(material, "baseColorTexture", None) or getattr(material, "image", None)
    uv = getattr(mesh.visual, "uv", None)
    if image is None or uv is None or len(uv) != len(mesh.vertices):
        tex = ctx.texture((1, 1), 4, bytes((255, 255, 255, 255)))
        return tex, np.zeros((len(mesh.vertices), 2), dtype="f4"), False
    pil = image.convert("RGBA") if isinstance(image, Image.Image) else Image.fromarray(np.asarray(image)).convert("RGBA")
    tex = ctx.texture(pil.size, 4, pil.tobytes())
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    return tex, np.asarray(uv, dtype="f4"), True


def render_qa_views(glb_path: str | Path, output_dir: str | Path, size: int = 512) -> dict:
    glb = Path(glb_path).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    meshes = _world_meshes(glb)
    all_vertices = np.vstack([np.asarray(mesh.vertices, dtype=np.float64) for mesh in meshes])
    ctx = moderngl.create_standalone_context()
    program = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
    ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
    results = {}
    try:
        for view in VIEWS:
            camera_data = _camera(all_vertices, view, size, size)
            framebuffer = ctx.simple_framebuffer((size, size), components=4)
            framebuffer.use()
            framebuffer.clear(0.075, 0.085, 0.105, 1.0, depth=1.0)
            for mesh in meshes:
                vertices = np.asarray(mesh.vertices, dtype=np.float64)
                clip = _project(vertices, camera_data)
                normals = np.asarray(mesh.vertex_normals, dtype=np.float64) @ camera_data["basis"].T
                texture, uv, textured = _texture(ctx, mesh)
                packed = np.column_stack([clip, normals.astype("f4"), uv, _rgba(mesh)]).astype("f4")
                vbo = ctx.buffer(packed.tobytes())
                ibo = ctx.buffer(np.asarray(mesh.faces, dtype="i4").tobytes())
                vao = ctx.vertex_array(program, [(vbo, "3f 3f 2f 4f", "in_position", "in_normal", "in_uv", "in_color")], ibo)
                texture.use(0)
                program["base_texture"].value = 0
                program["use_texture"].value = textured
                vao.render(moderngl.TRIANGLES)
                vao.release(); ibo.release(); vbo.release(); texture.release()
            raw = framebuffer.read(components=4, alignment=1)
            image = Image.frombytes("RGBA", (size, size), raw).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
            path = out / f"{view}.png"
            image.save(path, "PNG")
            results[view] = str(path)
            framebuffer.release()
    finally:
        program.release(); ctx.release()
    return {"views": results, "renderer": "moderngl-offscreen", "camera_fixed": True, "lighting_fixed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("glb")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    print("AIVF_QA_RENDERS|" + json.dumps(render_qa_views(args.glb, args.output_dir)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
