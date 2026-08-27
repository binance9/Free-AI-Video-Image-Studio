from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download, hf_hub_download

BASE = Path(__file__).resolve().parents[1]
CACHE = BASE / "data" / "models" / "image"
CACHE.mkdir(parents=True, exist_ok=True)

BASE_REPO = "stabilityai/stable-diffusion-xl-base-1.0"
LIGHTNING_REPO = "ByteDance/SDXL-Lightning"
LIGHTNING_FILE = "sdxl_lightning_4step_lora.safetensors"

ALLOW = [
    "*.json",
    "*.txt",
    "*.model",
    "*.safetensors",
    "*.bin",
]

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

def main() -> int:
    print("=" * 72)
    print("AI Video Factory - SDXL FAST/RESUME downloader")
    print("Cache:", CACHE)
    print("Existing partial files will be reused automatically.")
    print("HF token:", "available" if env("HF_TOKEN") else "not set (public download)")
    print("Xet:", "enabled unless explicitly disabled")
    print("=" * 72)

    started = time.time()
    try:
        print("\n[1/2] SDXL base - resume/cache download...")
        snapshot_download(
            repo_id=BASE_REPO,
            cache_dir=str(CACHE),
            allow_patterns=ALLOW,
            max_workers=12,
            force_download=False,
            local_files_only=False,
        )

        print("\n[2/2] SDXL-Lightning 4-step LoRA - resume/cache download...")
        hf_hub_download(
            repo_id=LIGHTNING_REPO,
            filename=LIGHTNING_FILE,
            cache_dir=str(CACHE),
            force_download=False,
            local_files_only=False,
        )
    except KeyboardInterrupt:
        print("\n[STOPPED] Download interrupted. Existing cache is kept.")
        return 130
    except Exception as exc:
        print("\n[ERROR]", type(exc).__name__, str(exc))
        print("You can run this downloader again; completed cache files are reused.")
        return 1

    elapsed = time.time() - started
    print("\n[OK] SDXL + Lightning cache ready.")
    print(f"Elapsed: {elapsed/60:.1f} minutes")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
