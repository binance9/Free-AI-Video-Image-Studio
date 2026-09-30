"""Check what diffusion models are cached locally."""
import os
from pathlib import Path

cache = Path(os.path.expanduser("~/.cache/huggingface/hub"))
targets = ["stabilityai", "Lykon", "dreamshaper", "stable-diffusion-xl"]
found = False

if cache.exists():
    for d in cache.iterdir():
        if "models--" in d.name:
            for t in targets:
                if t.lower() in d.name.lower():
                    found = True
                    snapshots = d / "snapshots"
                    if snapshots.exists():
                        for s in snapshots.iterdir():
                            has_index = (s / "model_index.json").exists()
                            size_mb = sum(f.stat().st_size for f in s.rglob("*") if f.is_file()) / 1e6
                            print(f"{d.name} -> {s.name} (model_index.json={has_index}, {size_mb:.0f}MB)")
    if not found:
        print("No SDXL/DreamShaper model cached")
        print("Available cached models:")
        for d in cache.iterdir():
            if "models--" in d.name:
                print(f"  {d.name}")
else:
    print("No HF cache directory found")
