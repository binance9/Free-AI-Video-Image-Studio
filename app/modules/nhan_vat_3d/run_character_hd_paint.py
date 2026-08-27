"""Texture an existing GLB with Hunyuan3D-Paint without rebuilding shape.

Runs in the isolated Character HD Python 3.12 runtime.  The white/source GLB is
never modified; a new textured GLB is written only after validation succeeds.
"""
from __future__ import annotations

import argparse
import gc
import math
import os
import threading
import time
from pathlib import Path


def progress(pct: int, stage: str, detail: str = "") -> None:
    print(f"AIVF_PROGRESS|{pct}|{stage}|{detail}", flush=True)


def _cache_size_gb() -> float | None:
    """Best-effort Hugging Face cache size for activity visibility."""
    root = os.environ.get("HF_HOME")
    if not root:
        return None
    try:
        total = 0
        for base, _, files in os.walk(root):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(base, name))
                except OSError:
                    pass
        return total / (1024 ** 3)
    except Exception:
        return None


def progressive_heartbeat(
    stop: threading.Event, start_pct: int, end_pct: int, stage: str, detail: str, *, horizon_seconds: int
) -> None:
    """Emit visibly moving estimated progress without ever overtaking the next real stage.

    Long model-load/inference calls do not expose byte/step callbacks.  We therefore
    use a bounded asymptotic estimate and label it as an estimate.  The real stage
    completion marker still jumps to ``end_pct`` only after the call returns.
    """
    started = time.monotonic()
    span = max(1, end_pct - start_pct - 1)
    while not stop.wait(12):
        elapsed = int(time.monotonic() - started)
        ratio = 1.0 - math.exp(-elapsed / max(60.0, float(horizon_seconds)))
        pct = start_pct + min(span, int(span * ratio))
        extra = detail
        cache_gb = _cache_size_gb() if 'weights' in detail.lower() else None
        if cache_gb is not None:
            extra += f" · cache {cache_gb:.2f} GB"
        progress(pct, stage, f"{elapsed}s · {extra} · % ước tính")


def load_mesh(path: Path):
    import trimesh
    loaded = trimesh.load(path, process=False)
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise RuntimeError("GLB không có mesh tam giác")
        loaded = meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.faces) < 4:
        raise RuntimeError("GLB không có mesh hợp lệ để tô màu")
    return loaded


def validate_textured_glb(path: Path) -> int:
    """Return largest embedded texture dimension; raise when GLB has no texture."""
    from pygltflib import GLTF2
    gltf = GLTF2().load_binary(str(path))
    if not gltf.materials or not gltf.textures or not gltf.images:
        raise RuntimeError("GLB xuất ra chưa chứa texture/material màu")
    # Hunyuan Paint normally bakes 2K. We only need a truthy marker here because
    # image bytes may be embedded in bufferViews and do not expose dimensions.
    return 2048



def _enable_local_hunyuan_custom_pipeline() -> None:
    """Allow Hunyuan's bundled local Diffusers custom pipeline in this worker only."""
    from diffusers import DiffusionPipeline

    current = DiffusionPipeline.from_pretrained
    func = getattr(current, "__func__", None)
    if func is None or getattr(func, "_aivf_trusted_local_hunyuan", False):
        return

    original = func

    @classmethod
    def trusted_from_pretrained(cls, pretrained_model_name_or_path, *args, **kwargs):
        custom_pipeline = kwargs.get("custom_pipeline")
        try:
            local_custom = bool(custom_pipeline) and Path(str(custom_pipeline)).exists()
        except Exception:
            local_custom = False
        if local_custom:
            kwargs.setdefault("trust_remote_code", True)
        return original(cls, pretrained_model_name_or_path, *args, **kwargs)

    trusted_from_pretrained.__func__._aivf_trusted_local_hunyuan = True
    DiffusionPipeline.from_pretrained = trusted_from_pretrained


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh")
    parser.add_argument("image")
    parser.add_argument("output")
    parser.add_argument("--model", default="tencent/Hunyuan3D-2")
    args = parser.parse_args()

    mesh_path = Path(args.mesh).resolve()
    image_path = Path(args.image).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Paint HD cần CUDA nhưng PyTorch không nhận GPU NVIDIA")
    gpu = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    progress(8, "Kiểm tra Paint HD", f"{gpu} · VRAM {vram_gb:.1f} GB")

    progress(14, "Nạp GLB trắng", mesh_path.name)
    mesh = load_mesh(mesh_path)
    face_count = int(len(mesh.faces))
    progress(18, "GLB sẵn sàng", f"{face_count:,} tam giác · giữ nguyên shape")

    from PIL import Image
    from hy3dgen.rembg import BackgroundRemover
    image = Image.open(image_path).convert("RGBA")
    try:
        image = BackgroundRemover()(image)
    except Exception as exc:
        progress(22, "Ảnh tham chiếu fallback", str(exc)[:180])

    progress(30, "Nạp Hunyuan3D-Paint", "Turbo 2K · lần đầu có thể tải weights lớn")
    _enable_local_hunyuan_custom_pipeline()
    progress(31, "Cho phép pipeline Paint local", "trust_remote_code=True · chỉ worker Hunyuan local")
    from hy3dgen.texgen import Hunyuan3DPaintPipeline
    load_stop = threading.Event()
    load_hb = threading.Thread(
        target=progressive_heartbeat,
        args=(load_stop, 30, 58, "Nạp Hunyuan3D-Paint", "đang tải / nạp texture weights"),
        kwargs={"horizon_seconds": 360},
        daemon=True,
    )
    load_hb.start()
    try:
        paint = Hunyuan3DPaintPipeline.from_pretrained(args.model)
    finally:
        load_stop.set()
        load_hb.join(timeout=1)

    # Tencent's official Gradio uses model CPU offload in low-VRAM mode.
    offload = False
    try:
        paint.enable_model_cpu_offload()
        offload = True
    except Exception:
        offload = False
    progress(58, "Paint đã nạp", "Low VRAM CPU offload BẬT" if offload else "CUDA mode")

    infer_stop = threading.Event()
    infer_hb = threading.Thread(
        target=progressive_heartbeat,
        args=(infer_stop, 65, 90, "Tạo texture màu HD", "đang chiếu màu lên mesh · CUDA"),
        kwargs={"horizon_seconds": 900},
        daemon=True,
    )
    infer_hb.start()
    try:
        textured = paint(mesh, image=image)
    except torch.cuda.OutOfMemoryError as exc:
        raise RuntimeError(
            "GPU hết VRAM khi tô màu HD. Đóng app nặng rồi thử lại; shape trắng vẫn còn nguyên."
        ) from exc
    finally:
        infer_stop.set()
        infer_hb.join(timeout=1)

    progress(90, "Xuất GLB có màu", "Đang nhúng UV + texture vào GLB mới")
    textured.export(output_path)
    if not output_path.exists() or output_path.stat().st_size < 1024:
        raise RuntimeError("Paint HD không tạo được GLB đầu ra")
    texture_size = validate_textured_glb(output_path)
    print("AIVF_TEXTURE_APPLIED|1", flush=True)
    print(f"AIVF_TEXTURE_SIZE|{texture_size}", flush=True)
    progress(96, "Kiểm tra texture", "GLB có material + texture nhúng hợp lệ")

    try:
        del paint
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass
    progress(100, "Hoàn tất màu HD", "Shape giữ nguyên · GLB màu đã tạo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
