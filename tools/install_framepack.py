"""Install FramePack (lllyasviel) — tao video AI dai tu 1 anh, chay local free.

Pattern theo tools/install_local_3d.py:
  - tools/external/FramePack     : source (git clone)
  - data/runtime_framepack/venv  : Python 3.10 venv rieng
  - READY.txt                    : marker cai xong

GPU: RTX 50-series (Blackwell) -> torch cu128 bat buoc (cu126 khong chay sm_120).
"""
from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "external"
DEST = TOOLS / "FramePack"
RUNTIME = ROOT / "data" / "runtime_framepack"
VENV = RUNTIME / "venv"
READY = RUNTIME / "READY.txt"

REPO = "https://github.com/lllyasviel/FramePack.git"
PY310 = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python310" / "python.exe"


def run(*args, cwd=None, check=True):
    print(">", " ".join(map(str, args)))
    r = subprocess.call(list(map(str, args)), cwd=str(cwd or ROOT))
    if check and r != 0:
        sys.exit(r)


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    TOOLS.mkdir(parents=True, exist_ok=True)

    # 1) source
    if not (DEST / "demo_gradio.py").exists():
        if DEST.exists():
            shutil.rmtree(DEST)
        run("git", "clone", "--depth", "1", REPO, DEST)
    else:
        print("[framepack] source da co, bo qua clone")

    # 2) venv Python 3.10
    if not PY310.exists():
        print("LOI: khong thay Python 3.10 tai", PY310)
        sys.exit(1)
    if not (VENV / "Scripts" / "python.exe").exists():
        run(PY310, "-m", "venv", VENV)
    vp = VENV / "Scripts" / "python.exe"

    # 3) torch cu128 (Blackwell 50-series) + deps cua FramePack
    run(vp, "-m", "pip", "install", "--upgrade", "pip", check=False)
    run(vp, "-m", "pip", "install", "torch", "torchvision", "torchaudio",
        "--index-url", "https://download.pytorch.org/whl/cu128")
    run(vp, "-m", "pip", "install", "-r", DEST / "requirements.txt")
    run(vp, "-m", "pip", "install", "huggingface_hub", "hf_transfer", check=False)

    # 4) danh dau READY
    READY.write_text("framepack ready\n", encoding="utf-8")
    print("\nFRAMEPACK DA CAI XONG.")
    print("  Chay: RUN_FRAMEPACK.bat  (mo GUI http://127.0.0.1:7890)")
    print("  Lan dau chay se tu tai model ~35GB vao HF cache (ai moi lan sau).")


if __name__ == "__main__":
    main()
