#!/usr/bin/env python3
"""Download Wan2.1 models for the AI Video Factory upgrade."""
import sys
import os
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

from huggingface_hub import snapshot_download

models = [
    "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
]

for model_id in models:
    print(f"\n{'='*60}")
    print(f"Downloading: {model_id}")
    print(f"{'='*60}")
    try:
        path = snapshot_download(
            repo_id=model_id,
            local_dir=None,  # use default cache
        )
        print(f"SUCCESS: {model_id} -> {path}")
    except Exception as e:
        print(f"ERROR downloading {model_id}: {e}")
        sys.exit(1)

print("\nAll models downloaded successfully!")
