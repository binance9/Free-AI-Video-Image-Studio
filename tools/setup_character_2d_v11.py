from __future__ import annotations
from pathlib import Path
import torch
from diffusers import AutoPipelineForText2Image

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "models" / "image"
CACHE.mkdir(parents=True, exist_ok=True)
MODEL = "Lykon/dreamshaper-8"

device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32
kwargs = {"torch_dtype": dtype, "cache_dir": str(CACHE)}
if device == "cuda":
    kwargs["variant"] = "fp16"
print("Model:", MODEL)
print("Device:", device)
print("Variant:", kwargs.get("variant", "default/full precision"))
print("Cache:", CACHE)
AutoPipelineForText2Image.from_pretrained(MODEL, **kwargs)
print("DreamShaper 8 cache ready")
