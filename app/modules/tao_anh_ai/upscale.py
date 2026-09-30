"""Local image sizing and upscaling helpers; no paid API is used."""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image, ImageOps

_TARGET_SIZES = {
    "1024x1024": (1024, 1024),
    "1536x1024": (1536, 1024),
    "1024x1536": (1024, 1536),
    "2048x1152": (2048, 1152),
    "2048x2048": (2048, 2048),
    "3840x2160": (3840, 2160),
    "2160x3840": (2160, 3840),
}


def target_dimensions(target_size: str) -> tuple[int, int]:
    dims = _TARGET_SIZES.get(target_size)
    if not dims:
        raise ValueError("Kich thuoc AI anh khong hop le")
    return dims


def generation_dimensions(target_size: str) -> tuple[int, int]:
    """Keep SD 1.5 generation light, then finish to requested HD size locally."""
    width, height = target_dimensions(target_size)
    if width == height:
        return 512, 512
    return (640, 384) if width > height else (384, 640)


# ---------------------------------------------------------------------------
# RealESRGAN 4x upscaling (720p → 4K)
# ---------------------------------------------------------------------------
_REALESRGAN_AVAILABLE: bool | None = None


def _realesrgan_is_available() -> bool:
    """Check whether the RealESRGAN package is importable."""
    global _REALESRGAN_AVAILABLE
    if _REALESRGAN_AVAILABLE is not None:
        return _REALESRGAN_AVAILABLE
    try:
        import realesrgan  # noqa: F401
        from basicsr.archs.rrdbnet_arch import RRDBNet  # noqa: F401
        _REALESRGAN_AVAILABLE = True
    except ImportError:
        _REALESRGAN_AVAILABLE = False
    return _REALESRGAN_AVAILABLE


def _realesrgan_model_path() -> Path:
    """Resolve the RealESRGAN_x4plus model weights path.

    Looks in the HF cache under the model dir first, then in common
    ``data/runtime_character_hd/models/RealESRGAN`` locations.
    """
    candidates: list[Path] = []
    # Check HF cache style path
    model_dir = Path(os.getenv("AIVF_IMAGE_MODEL_DIR", "data/runtime_character_hd/models"))
    candidates.append(model_dir / "RealESRGAN_x4plus.pth")
    # Common download locations
    candidates.append(Path("models") / "RealESRGAN_x4plus.pth")
    candidates.append(Path("data/runtime_character_hd/models/RealESRGAN_x4plus.pth"))
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]  # Return first candidate even if it doesn't exist yet


def upscale_realesrgan(image: Image.Image, scale: int = 4, *, tile: int = 512, progress=None) -> Image.Image:
    """Upscale an image using RealESRGAN_x4plus (SRResNet, ~4x).

    Designed for 720p diffusion output → 4K delivery.
    Falls back to LANCZOS resize if RealESRGAN is not installed.

    Parameters
    ----------
    image : PIL.Image
        Input image (RGB recommended).
    scale : int
        Upscale factor (4 for 4x, 2 for 2x). Default 4.
    tile : int
        Tile size for memory-efficient inference. 512 is safe for 16 GB VRAM.
    progress : callable | None
        Optional ``progress(pct, stage, detail)`` callback.

    Returns
    -------
    PIL.Image
        Upscaled image in RGB mode.
    """
    image = image.convert("RGB")
    if progress:
        progress(50, "RealESRGAN upscale", f"Loading model (scale {scale}x)")

    if not _realesrgan_is_available():
        # Graceful fallback: high-quality LANCZOS resize
        if progress:
            progress(60, "Upscale (LANCZOS fallback)", "RealESRGAN not installed, using LANCZOS")
        new_size = (image.width * scale, image.height * scale)
        return image.resize(new_size, Image.Resampling.LANCZOS)

    import numpy as np

    # Build the RRDBNet architecture and load weights
    from basicsr.archs.rrdbnet_arch import RRDBNet
    import torch

    if progress:
        progress(55, "RealESRGAN upscale", "Building RRDBNet architecture")

    model = RRDBNet(
        num_in_ch=3, num_out_ch=3, num_feat=64,
        num_block=23, num_grow_ch=32, scale=scale,
    )

    weights_path = _realesrgan_model_path()
    if not weights_path.is_file():
        # Auto-download from GitHub releases if missing
        if progress:
            progress(58, "RealESRGAN upscale", "Downloading model weights")
        _download_realesrgan_weights(weights_path)

    if progress:
        progress(62, "RealESRGAN upscale", f"Loading weights from {weights_path.name}")
    state_dict = torch.load(str(weights_path), map_location="cpu")
    if "params" in state_dict:
        state_dict = state_dict["params"]
    # Handle key prefix differences
    new_state = {}
    for k, v in state_dict.items():
        new_k = k.replace("params_ema.", "") if k.startswith("params_ema.") else k
        new_state[new_k] = v
    model.load_state_dict(new_state, strict=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()

    if progress:
        progress(65, "RealESRGAN upscale", f"Inference on {device} (tile={tile})")

    # Use the official realesrgan package for tiled inference
    from realesrgan import RealESRGANer

    upsampler = RealESRGANer(
        scale=scale, model_path=str(weights_path),
        model=model, tile=tile, tile_pad=10,
        half=torch.cuda.is_available(),  # fp16 on GPU
        device=device,
    )
    img_np = np.array(image)  # HWC, uint8
    output_np, _ = upsampler.enhance(img_np, outscale=scale)
    result = Image.fromarray(output_np, "RGB")

    if progress:
        progress(95, "RealESRGAN upscale", f"Done: {result.width}x{result.height}")
    return result


def _download_realesrgan_weights(target: Path) -> None:
    """Download RealESRGAN_x4plus weights from GitHub releases."""
    import urllib.request

    target.parent.mkdir(parents=True, exist_ok=True)
    url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
    urllib.request.urlretrieve(url, str(target))


def finalize_pil(image: Image.Image, target_size: str, *, use_realesrgan: bool = False, progress=None) -> bytes:
    """Resize/upscale image to the requested target size and return PNG bytes.

    Parameters
    ----------
    image : PIL.Image
        Source image from the diffusion pipeline.
    target_size : str
        Key in ``_TARGET_SIZES`` (e.g. ``"3840x2160"`` for 4K).
    use_realesrgan : bool
        If True and the target is >= 4K, apply RealESRGAN 4x before fitting.
    progress : callable | None
        Optional progress callback for upscale stages.
    """
    dims = target_dimensions(target_size)
    source = image.convert("RGB")

    # Auto-enable RealESRGAN for 4K+ targets when source is small
    if use_realesrgan or (dims[0] >= 3840 and source.width < dims[0]):
        if progress:
            progress(40, "Upscaling", "RealESRGAN 4x upscale")
        source = upscale_realesrgan(source, scale=4, progress=progress)

    image = ImageOps.fit(source, dims, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()
