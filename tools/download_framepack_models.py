"""Tai before model cho FramePack — chay rieng, log ro rang, retry tu dong.

Cache: C:\\Users\\BAOAN\\.cache\\huggingface (ngoai OneDrive).
Chay: venv python tools/download_framepack_models.py
"""
import os, sys, time

os.environ["HF_HOME"] = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ["HF_HUB_DISABLE_XET"] = "1"  # xet bi ket tren may nay, HTTP thuong nhanh on

from huggingface_hub import snapshot_download

JOBS = [
    ("lllyasviel/FramePackI2V_HY", None),  # transformer 13B (~26GB, 3 shard)
    ("lllyasviel/flux_redux_bfl", ["feature_extractor/*", "image_encoder/*"]),
    ("hunyuanvideo-community/HunyuanVideo",
     ["text_encoder/*", "text_encoder_2/*", "tokenizer/*", "tokenizer_2/*", "vae/*"]),
]

for repo, patterns in JOBS:
    for attempt in range(1, 6):
        print(f"\n===== {repo} (lan thu {attempt}) =====", flush=True)
        t0 = time.time()
        try:
            p = snapshot_download(repo_id=repo, allow_patterns=patterns,
                                  max_workers=4)
            print(f"OK {repo} trong {round((time.time()-t0)/60,1)} phut -> {p}", flush=True)
            break
        except Exception as e:
            print(f"LOI {repo}: {e}", flush=True)
            time.sleep(10 * attempt)
    else:
        print(f"THAT BAI {repo} sau 5 lan — chay lai script se tiep tuc (download co resume).", flush=True)
        sys.exit(1)

print("\nTAI MODEL XONG HET — FramePack san sang.", flush=True)
