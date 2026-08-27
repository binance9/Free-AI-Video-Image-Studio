from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime_video_cleanup"
VENV = RUNTIME / "venv"
PYEXE = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQ = ROOT / "requirements_video_cleanup.txt"
MODELS = ROOT / "data" / "models" / "video_cleanup"


def run(cmd, check=True):
    print("[RUN]", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), check=check)


def main():
    print("=" * 64)
    print(" AI VIDEO FACTORY - VIDEO CLEANUP AI SETUP 0.8.7.7")
    print(" Xoa nen video AI + inpaint chu/icon local")
    print("=" * 64)
    if not (sys.version_info >= (3, 11) and sys.version_info < (3, 14)):
        print("[LOI] Can Python 3.11, 3.12 hoac 3.13. Khuyen nghi 3.12.")
        return 1
    RUNTIME.mkdir(parents=True, exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True)
    if not PYEXE.is_file():
        print("[1/4] Tao runtime rieng...")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    print("[2/4] Nang pip...")
    run([PYEXE, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    print("[3/4] Cai rembg + OpenCV + ONNX Runtime GPU CUDA 12...")
    try:
        run([PYEXE, "-m", "pip", "install", "-r", REQ])
    except subprocess.CalledProcessError:
        print("[WARN] GPU runtime cai loi, fallback CPU de van dung duoc.")
        run([PYEXE, "-m", "pip", "uninstall", "-y", "onnxruntime-gpu"], check=False)
        run([PYEXE, "-m", "pip", "install", "rembg>=2.0.67", "opencv-python-headless>=4.10", "onnxruntime>=1.19", "Pillow>=10.4"])
    print("[4/4] Self-test...")
    code = "import cv2,rembg,onnxruntime as ort; print('providers=',ort.get_available_providers()); print('VIDEO_CLEANUP_OK')"
    env = {**os.environ, "U2NET_HOME": str(MODELS)}
    proc = subprocess.run([str(PYEXE), "-c", code], text=True, env=env)
    if proc.returncode != 0:
        print("[LOI] Runtime Video Cleanup chua san sang.")
        return proc.returncode
    print("[OK] VIDEO CLEANUP AI DA SAN SANG.")
    print("Lan dau xoa nen, model se tu tai vao data\\models\\video_cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
