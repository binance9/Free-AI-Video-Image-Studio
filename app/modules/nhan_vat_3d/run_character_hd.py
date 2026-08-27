"""Standalone runner for Hunyuan3D-2mini.

Runs inside its own venv so the main FastAPI environment stays isolated.
Prints AIVF_PROGRESS markers for the parent job manager.
"""
from __future__ import annotations

import argparse
import gc
import os
import threading
import time
from pathlib import Path


def progress(pct: int, stage: str, detail: str = "") -> None:
    print(f"AIVF_PROGRESS|{pct}|{stage}|{detail}", flush=True)


def _dir_size_bytes(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def _model_load_heartbeat(stop: threading.Event, cache_root: Path) -> None:
    """Show that from_pretrained is alive while HF downloads/loads silently."""
    started = time.monotonic()
    while not stop.wait(8):
        elapsed = int(time.monotonic() - started)
        gb = _dir_size_bytes(cache_root) / (1024 ** 3) if cache_root.exists() else 0.0
        progress(28, "Đang tải / nạp weights HD", f"{elapsed}s · cache Character HD {gb:.2f} GB")


def _inference_heartbeat(stop: threading.Event, gpu_name: str) -> None:
    """Keep UI/watchdog alive while the CUDA shape call is intentionally silent."""
    started = time.monotonic()
    while not stop.wait(12):
        elapsed = int(time.monotonic() - started)
        progress(50, "Dựng hình khối HD", f"{elapsed}s · {gpu_name} đang suy luận CUDA")


def _texture_load_heartbeat(stop: threading.Event) -> None:
    """Texture weights can also download/load silently on first use."""
    started = time.monotonic()
    while not stop.wait(12):
        elapsed = int(time.monotonic() - started)
        progress(70, "Nạp Hunyuan3D-Paint", f"{elapsed}s · đang tải / nạp texture weights")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("output")
    parser.add_argument("--texture", action="store_true")
    parser.add_argument("--optimize-light", action="store_true")
    parser.add_argument("--mesh-profile", choices=("hd", "medium", "light"), default="hd")
    parser.add_argument("--model", default="tencent/Hunyuan3D-2mini")
    parser.add_argument("--subfolder", default="hunyuan3d-dit-v2-mini")
    args = parser.parse_args()

    image_path = Path(args.image).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    progress(8, "Nạp Character HD", args.model)
    from PIL import Image
    import torch
    from hy3dgen.rembg import BackgroundRemover
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("Character HD cần CUDA nhưng PyTorch không nhận GPU NVIDIA")

    device = "cuda"
    gpu_name = torch.cuda.get_device_name(0)
    try:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    except Exception:
        vram_gb = 0.0
    progress(12, "GPU Character HD sẵn sàng", f"{gpu_name} · VRAM {vram_gb:.1f} GB · FP16")

    progress(16, "Chuẩn hóa ảnh", "Tách nền và căn nhân vật")
    image = Image.open(image_path).convert("RGBA")
    try:
        image = BackgroundRemover()(image)
    except Exception as exc:
        progress(20, "Tách nền fallback", str(exc)[:180])

    progress(28, "Nạp model hình khối HD", f"{args.subfolder} · CUDA + FP16")
    cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    stop = threading.Event()
    heartbeat = threading.Thread(target=_model_load_heartbeat, args=(stop, cache_root), daemon=True)
    heartbeat.start()
    try:
        # Match Tencent's official mini example/server: FP16 + explicit CUDA device.
        shape = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            args.model,
            subfolder=args.subfolder,
            variant="fp16",
            use_safetensors=True,
            device=device,
        )
    finally:
        stop.set()
        heartbeat.join(timeout=1)

    progress(44, "Model HD đã nạp", f"{gpu_name} · FP16")
    progress(50, "Dựng hình khối HD", "Hunyuan3D-2mini đang suy luận")
    infer_stop = threading.Event()
    infer_heartbeat = threading.Thread(target=_inference_heartbeat, args=(infer_stop, gpu_name), daemon=True)
    infer_heartbeat.start()
    try:
        mesh = shape(
            image=image,
            num_inference_steps=50,
            octree_resolution=380,
            num_chunks=20000,
            generator=torch.manual_seed(12345),
            output_type="trimesh",
        )[0]
    except torch.cuda.OutOfMemoryError as exc:
        raise RuntimeError(
            "GPU hết VRAM khi dựng Character HD. Hãy đóng app/game nặng rồi thử lại; "
            "nếu vẫn lỗi thì cần chế độ Low VRAM."
        ) from exc
    finally:
        infer_stop.set()
        infer_heartbeat.join(timeout=1)

    if args.optimize_light:
        profile_labels = {"hd": "HD", "medium": "Medium", "light": "Light"}
        profile_targets = {"hd": "~65-75%", "medium": "~25-35%", "light": "~10-18%"}
        profile_label = profile_labels.get(args.mesh_profile, "HD")
        progress(62, f"Tối ưu mesh · {profile_label}", f"Mục tiêu {profile_targets.get(args.mesh_profile, '~65-75%')} tam giác")
        try:
            from mesh_optimize_profiles import optimize_mesh_profile
            mesh, opt_stats = optimize_mesh_profile(mesh, args.mesh_profile)
            before = int(opt_stats.get("faces_before", len(mesh.faces)))
            after = int(opt_stats.get("faces_after", len(mesh.faces)))
            print(f"AIVF_MESH_OPTIMIZED|{before}|{after}|{args.mesh_profile}", flush=True)
            if opt_stats.get("optimized"):
                progress(65, f"Mesh {profile_label} đã xong", f"{before:,} → {after:,} tam giác")
            else:
                progress(65, f"Mesh {profile_label} đã đủ nhẹ", f"Giữ nguyên {after:,} tam giác")
        except Exception as exc:
            # Optimization is optional: never throw away a good HD mesh.
            print(f"AIVF_MESH_OPTIMIZED|0|0|{args.mesh_profile}", flush=True)
            progress(65, "Bỏ qua tối ưu mesh", str(exc)[:240])

    progress(66, "Mesh HD đã xong", "Đang giải phóng VRAM shape model")
    try:
        del shape
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass

    texture_applied = False
    if args.texture:
        progress(70, "Nạp Hunyuan3D-Paint", "Chuẩn bị texture màu HD")
        try:
            texture_stop = threading.Event()
            texture_heartbeat = threading.Thread(target=_texture_load_heartbeat, args=(texture_stop,), daemon=True)
            texture_heartbeat.start()
            try:
                from hy3dgen.texgen import Hunyuan3DPaintPipeline
                paint = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")
            finally:
                texture_stop.set()
                texture_heartbeat.join(timeout=1)
            progress(82, "Tạo texture HD", "Đang chiếu màu lên mesh")
            mesh = paint(mesh, image=image)
            texture_applied = True
            try:
                del paint
                gc.collect()
                torch.cuda.empty_cache()
            except Exception:
                pass
        except Exception as exc:
            # Shape remains usable when native texture extensions are unavailable on Windows.
            progress(84, "Texture HD chưa sẵn sàng", str(exc)[:400])

    print(f"AIVF_TEXTURE_APPLIED|{1 if texture_applied else 0}", flush=True)
    progress(94, "Xuất GLB HD", str(output_path))
    mesh.export(output_path)
    if not output_path.exists() or output_path.stat().st_size < 512:
        raise RuntimeError("Character HD không tạo được GLB hợp lệ")
    progress(100, "Hoàn tất Character HD", "GLB đã tạo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
