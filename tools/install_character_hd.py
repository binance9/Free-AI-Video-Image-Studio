"""One-time Windows installer for the optional Character HD backend.

Keeps Hunyuan3D in an isolated venv and external source folder so it does not
change the existing TripoSR runtime.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime_character_hd"
VENV = RUNTIME / "venv"
EXTERNAL = ROOT / "tools" / "external"
DEST = EXTERNAL / "Hunyuan3D-2"
ZIP_URL = "https://github.com/Tencent-Hunyuan/Hunyuan3D-2/archive/refs/heads/main.zip"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> int:
    print("[RUN]", " ".join(map(str, args)), flush=True)
    proc = subprocess.run(list(map(str, args)), cwd=str(cwd or ROOT))
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, args)
    return proc.returncode


def vpy() -> Path:
    return VENV / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def download_source() -> None:
    if (DEST / "hy3dgen").exists():
        print("[OK] Hunyuan3D-2 source da co.")
        return
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aivf_hy3d_") as td:
        archive = Path(td) / "hunyuan.zip"
        print("[1/5] Dang tai Hunyuan3D-2 source chinh thuc...", flush=True)
        urllib.request.urlretrieve(ZIP_URL, archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(td)
        folders = [p for p in Path(td).iterdir() if p.is_dir() and p.name.startswith("Hunyuan3D-2")]
        if not folders:
            raise RuntimeError("Khong tim thay thu muc Hunyuan3D-2 sau khi giai nen")
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.copytree(folders[0], DEST)


def install_texture_extensions(python: Path) -> bool:
    ok = True
    for rel in [
        Path("hy3dgen/texgen/custom_rasterizer"),
        Path("hy3dgen/texgen/differentiable_renderer"),
    ]:
        folder = DEST / rel
        if not folder.exists():
            print(f"[WARN] Khong thay {rel}; bo qua texture extension.")
            ok = False
            continue
        code = run(str(python), "setup.py", "install", cwd=folder, check=False)
        if code != 0:
            print(f"[WARN] Texture extension chua build duoc: {rel}")
            ok = False
    return ok


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print(f"[LOI] Character HD can Python 3.12. Hien tai: {sys.version.split()[0]}")
        print("Hay chay SETUP_CHARACTER_HD.bat de no tu chon Python 3.12.")
        return 2

    RUNTIME.mkdir(parents=True, exist_ok=True)
    download_source()

    print("[2/5] Tao moi truong Python rieng cho Character HD...", flush=True)
    if not vpy().exists():
        run(sys.executable, "-m", "venv", str(VENV))
    python = vpy()

    print("[3/5] Cai PyTorch CUDA va dependencies...", flush=True)
    run(str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    run(str(python), "-m", "pip", "install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu128")
    req = DEST / "requirements.txt"
    if req.exists():
        run(str(python), "-m", "pip", "install", "-r", str(req))
    run(str(python), "-m", "pip", "install", "-e", str(DEST))

    print("[4/5] Self-test Character HD shape backend...", flush=True)
    test = (
        "import torch; import hy3dgen; "
        "from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline; "
        "print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'hy3dgen OK')"
    )
    run(str(python), "-c", test)
    (RUNTIME / "READY.txt").write_text("character_hd_shape_ready\n", encoding="utf-8")

    print("[5/5] Thu cai texture HD (optional)...", flush=True)
    texture_ok = install_texture_extensions(python)
    if texture_ok:
        texture_test = (
            "import custom_rasterizer_kernel; import mesh_processor; "
            "from hy3dgen.texgen import Hunyuan3DPaintPipeline; print('TEXTURE_NATIVE_OK')"
        )
        texture_ok = run(str(python), "-c", texture_test, check=False) == 0
    if texture_ok:
        (RUNTIME / "TEXTURE_READY.txt").write_text("character_hd_texture_ready_v0867\n", encoding="utf-8")
        print("[OK] CHARACTER HD + TEXTURE da san sang.")
    else:
        (RUNTIME / "TEXTURE_READY.txt").unlink(missing_ok=True)
        print("[OK] CHARACTER HD SHAPE da san sang.")
        print("[WARN] Texture HD native chua build. Chay SETUP_CHARACTER_HD_TEXTURE.bat de thu build rieng Paint.")

    print("Lan dau dung Character HD, model weights se tu tai ve may.")
    print("Mo START_VIDEO_FACTORY.bat va chon Backend 3D: Nhan vat HD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
