"""Install free local TripoSR in an isolated Python 3.12 runtime on Windows."""
from __future__ import annotations
import os, re, shutil, subprocess, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "external"
DEST = TOOLS / "TripoSR"
RUNTIME = ROOT / "data" / "runtime3d"
VENV = RUNTIME / "venv"
READY = RUNTIME / "READY.txt"
DEVICE_FILE = RUNTIME / "DEVICE.txt"

TRIPOSR_ZIP = "https://github.com/VAST-AI-Research/TripoSR/archive/refs/heads/main.zip"
PY312_URL = "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"

PATCHED_REQUIREMENTS = """omegaconf==2.3.0
Pillow>=11.3.0,<13
einops>=0.7,<0.9
transformers>=4.35,<5
trimesh>=4.0,<5
rembg
huggingface-hub
imageio[ffmpeg]
xatlas
moderngl
PyMCubes==0.1.6
onnxruntime
"""

ISOSURFACE_PATCH = 'from typing import Optional, Tuple\n\nimport numpy as np\nimport torch\nimport torch.nn as nn\nimport mcubes\n\n\nclass IsosurfaceHelper(nn.Module):\n    points_range: Tuple[float, float] = (0, 1)\n\n    @property\n    def grid_vertices(self) -> torch.FloatTensor:\n        raise NotImplementedError\n\n\nclass MarchingCubeHelper(IsosurfaceHelper):\n    # Cross-platform PyMCubes fallback. Neural inference can still use CUDA.\n    def __init__(self, resolution: int) -> None:\n        super().__init__()\n        self.resolution = resolution\n        self._grid_vertices: Optional[torch.FloatTensor] = None\n\n    @property\n    def grid_vertices(self) -> torch.FloatTensor:\n        if self._grid_vertices is None:\n            x, y, z = (\n                torch.linspace(*self.points_range, self.resolution),\n                torch.linspace(*self.points_range, self.resolution),\n                torch.linspace(*self.points_range, self.resolution),\n            )\n            x, y, z = torch.meshgrid(x, y, z, indexing="ij")\n            verts = torch.cat(\n                [x.reshape(-1, 1), y.reshape(-1, 1), z.reshape(-1, 1)], dim=-1\n            ).reshape(-1, 3)\n            self._grid_vertices = verts\n        return self._grid_vertices\n\n    def forward(self, level: torch.FloatTensor) -> Tuple[torch.FloatTensor, torch.LongTensor]:\n        level = -level.view(self.resolution, self.resolution, self.resolution)\n        volume = level.detach().float().cpu().numpy()\n        verts, faces = mcubes.marching_cubes(volume, 0.0)\n        v_pos = torch.from_numpy(np.asarray(verts)).float()\n        t_pos_idx = torch.from_numpy(np.asarray(faces)).long()\n        v_pos = v_pos[..., [2, 1, 0]]\n        v_pos = v_pos / (self.resolution - 1.0)\n        return v_pos.to(level.device), t_pos_idx.to(level.device)\n'

def run(*args, cwd=None):
    print(">", " ".join(map(str, args)))
    subprocess.check_call(list(map(str, args)), cwd=str(cwd or ROOT))

def capture(*args):
    try:
        return subprocess.check_output(list(map(str, args)), text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return ""

def find_python312():
    candidates = []
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
    candidates.append(local)
    py = shutil.which("py")
    if py:
        out = capture(py, "-3.12", "-c", "import sys;print(sys.executable)")
        if out:
            candidates.append(Path(out.splitlines()[-1].strip()))
    for p in candidates:
        if p and p.exists():
            return p.resolve()
    return None

def install_python312():
    print("\n[1/7] Cai Python 3.12 rieng cho AI 3D...")
    cache = ROOT / "tools" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    exe = cache / "python-3.12.9-amd64.exe"
    if not exe.exists():
        print("Dang tai Python 3.12.9 tu python.org...")
        urllib.request.urlretrieve(PY312_URL, exe)
    run(str(exe), "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_test=0",
        "Include_launcher=1", "SimpleInstall=1")
    found = find_python312()
    if not found:
        raise RuntimeError("Da cai Python 3.12 nhung khong tim thay python.exe")
    return found

def ensure_venv(py312):
    py = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        print("\n[2/7] Tao moi truong runtime3d rieng...")
        RUNTIME.mkdir(parents=True, exist_ok=True)
        run(str(py312), "-m", "venv", str(VENV))
    return py

def install_torch(py):
    print("\n[3/7] Cai PyTorch...")
    smi = capture("nvidia-smi") if shutil.which("nvidia-smi") else ""
    device = "cpu"
    index = "https://download.pytorch.org/whl/cpu"
    if smi:
        device = "cuda"
        m = re.search(r"CUDA Version:\s*([0-9]+)\.([0-9]+)", smi)
        cuda = (int(m.group(1)), int(m.group(2))) if m else (11, 8)
        suffix = "cu128" if cuda >= (12,8) else ("cu126" if cuda >= (12,6) else "cu118")
        index = f"https://download.pytorch.org/whl/{suffix}"
        print("NVIDIA GPU phat hien ->", suffix)
    else:
        print("Khong phat hien NVIDIA -> dung CPU, se cham hon.")
    run(str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    run(str(py), "-m", "pip", "install", "torch==2.7.1", "torchvision==0.22.1", "--index-url", index)
    return device

def fetch_triposr():
    print("\n[4/7] Chuan bi TripoSR...")
    TOOLS.mkdir(parents=True, exist_ok=True)
    if not (DEST / "run.py").exists():
        archive = TOOLS / "triposr-main.zip"
        urllib.request.urlretrieve(TRIPOSR_ZIP, archive)
        temp = TOOLS / "_triposr_extract"
        shutil.rmtree(temp, ignore_errors=True)
        temp.mkdir(parents=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(temp)
        extracted = next(temp.glob("TripoSR-*"))
        shutil.rmtree(DEST, ignore_errors=True)
        shutil.move(str(extracted), str(DEST))
        shutil.rmtree(temp, ignore_errors=True)
        archive.unlink(missing_ok=True)

def patch_triposr():
    print("\n[5/7] Patch Windows: Pillow moi + PyMCubes, bo torchmcubes...")
    req = DEST / "requirements_aivf_windows.txt"
    req.write_text(PATCHED_REQUIREMENTS, encoding="utf-8")
    iso = DEST / "tsr" / "models" / "isosurface.py"
    iso.write_text(ISOSURFACE_PATCH, encoding="utf-8")
    return req

def install_dependencies(py, req):
    print("\n[6/7] Cai dependency da sua...")
    run(str(py), "-m", "pip", "install", "-r", str(req))

def verify(py, device):
    print("\n[7/7] Self-test runtime3d...")
    code = (
        "import numpy as np, torch, PIL, mcubes, transformers, trimesh, rembg;"
        "v=np.zeros((20,20,20),dtype=np.float32);"
        "x,y,z=np.ogrid[:20,:20,:20];"
        "v[((x-10)**2+(y-10)**2+(z-10)**2)<36]=1;"
        "a,b=mcubes.marching_cubes(v,0.5);"
        "assert len(a)>0 and len(b)>0;"
        "print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'mesh',len(a),len(b))"
    )
    run(str(py), "-c", code)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    DEVICE_FILE.write_text(device, encoding="utf-8")
    READY.write_text("AIVF 0.8.2 runtime3d ready\npython="+str(py)+"\ndevice="+device+"\n", encoding="utf-8")

def main():
    print("="*72)
    print(" AI VIDEO FACTORY 0.8.2 - WINDOWS 3D FIX")
    print(" Python 3.12 rieng + PyMCubes. Khong dung Python 3.14 cho TripoSR.")
    print("="*72)
    READY.unlink(missing_ok=True)
    py312 = find_python312() or install_python312()
    print("Python 3D:", py312)
    py = ensure_venv(py312)
    device = install_torch(py)
    fetch_triposr()
    req = patch_triposr()
    install_dependencies(py, req)
    verify(py, device)
    print("\n[OK] AI 3D LOCAL DA CAI XONG.")
    print("Lan dau tao 3D, model weights se tu tai mien phi.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("\n[LOI]", exc)
        raise
