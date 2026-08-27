"""Build/validate optional Hunyuan3D-Paint native extensions on Windows.

0.8.7.6 goals:
- preserve the existing Character HD shape runtime/models;
- stage native source on an ASCII-only path;
- bridge torch headers/libs through an ASCII hardlink/copy mirror so MSVC can resolve torch/extension.h;
- auto-patch older upstream Windows-incompatible custom_rasterizer source patterns;
- capture the COMPLETE compiler output to data/runtime_character_hd/paint_build.log.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime_character_hd"
VENV = RUNTIME / "venv"
DEST = ROOT / "tools" / "external" / "Hunyuan3D-2"
READY = RUNTIME / "TEXTURE_READY.txt"
LOG = RUNTIME / "paint_build.log"


def vpy() -> Path:
    return VENV / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def log_line(text: str = "") -> None:
    print(text, flush=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", errors="replace") as f:
        f.write(text + "\n")


def run(*args: str, cwd: Path | None = None) -> int:
    cmd = list(map(str, args))
    log_line("[RUN] " + " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("DISTUTILS_USE_SDK", "1")
    env.setdefault("MSSdk", "1")
    env.setdefault("MAX_JOBS", "2")
    # PyTorch 2.9+ headers on Windows can hit C2872 (ambiguous `std`) when
    # compiled by NVCC through torch/extension.h.  PyTorch ships a Windows
    # CUDA guard keyed by USE_CUDA; inject it globally into nvcc without
    # modifying the user's installed Torch headers. NVIDIA documents
    # NVCC_APPEND_FLAGS as the supported way to append flags to all nvcc calls.
    if sys.platform.startswith("win"):
        current = env.get("NVCC_APPEND_FLAGS", "").strip()
        flag = "-DUSE_CUDA"
        if flag not in current.split():
            env["NVCC_APPEND_FLAGS"] = (current + " " + flag).strip()
    # Compile only for the visible GPU when possible, which makes Windows builds faster.
    try:
        if "TORCH_CUDA_ARCH_LIST" not in env:
            probe = subprocess.run(
                [str(vpy()), "-c", "import torch; c=torch.cuda.get_device_capability(); print(f'{c[0]}.{c[1]}')"],
                capture_output=True, text=True, timeout=20, env=env,
            )
            cap = probe.stdout.strip()
            if re.fullmatch(r"\d+\.\d+", cap):
                env["TORCH_CUDA_ARCH_LIST"] = cap
                log_line(f"[GPU] TORCH_CUDA_ARCH_LIST={cap}")
    except Exception:
        pass

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd or ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    with LOG.open("a", encoding="utf-8", errors="replace") as f:
        for line in proc.stdout:
            print(line, end="", flush=True)
            f.write(line)
    return proc.wait()


def path_is_ascii(path: Path) -> bool:
    try:
        str(path).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def ascii_build_root() -> Path:
    """Return a short ASCII-only build root for native Windows extensions.

    PyTorch's Ninja generator can mis-handle source/build paths containing
    Vietnamese characters (for example OneDrive\\Máy tính), producing paths
    like `M y t nh` and then reporting existing .cpp files as missing.
    """
    candidates: list[Path] = []
    configured = os.environ.get("AIVF_NATIVE_BUILD_ROOT", "").strip()
    if configured:
        candidates.append(Path(configured))
    if sys.platform.startswith("win"):
        system_drive = os.environ.get("SystemDrive", "C:")
        candidates.append(Path(system_drive + r"\\AIVF_NATIVE_BUILD"))
    temp = Path(tempfile.gettempdir()) / "AIVF_NATIVE_BUILD"
    candidates.append(temp)

    for candidate in candidates:
        if not path_is_ascii(candidate):
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise RuntimeError("Khong tao duoc thu muc build ASCII cho native extension")


def _mirror_tree_ascii(source: Path, alias: Path) -> Path:
    """Expose a Unicode source tree at an ASCII path without junctions.

    Windows directory-junction creation can fail when the target contains Vietnamese Unicode
    characters (for example OneDrive\\Máy tính).  Build a lightweight mirror
    instead: prefer NTFS hardlinks (zero duplicate file data on the same
    volume), falling back to copy2 only when a hardlink is unavailable.
    """
    # Remove a previous real directory or a stale junction from 0.8.7.3.
    try:
        is_junction = bool(getattr(alias, "is_junction", lambda: False)())
    except OSError:
        is_junction = False
    if is_junction or alias.is_symlink():
        try:
            os.rmdir(alias)
        except OSError:
            pass
    elif alias.exists():
        shutil.rmtree(alias, ignore_errors=True)
    # Broken reparse points may report exists=False; rmdir is harmless if absent.
    if os.path.lexists(alias):
        try:
            os.rmdir(alias)
        except OSError:
            pass
    alias.mkdir(parents=True, exist_ok=True)
    linked = copied = 0
    for src in source.rglob("*"):
        rel = src.relative_to(source)
        dst = alias / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
            linked += 1
        except OSError:
            shutil.copy2(src, dst)
            copied += 1
    if not any(alias.rglob("*")):
        raise RuntimeError(f"ASCII mirror rong: {alias}")
    log_line(f"[ASCII-MIRROR] {source} -> {alias} (hardlink={linked}, copy={copied})")
    return alias

def prepare_ascii_torch_bridge() -> tuple[Path, Path] | None:
    """Expose torch headers/libs through ASCII-only mirrored paths for MSVC/Ninja.

    Staging the C++ source alone is not enough when the virtualenv lives under
    `OneDrive\\Máy tính`: torch.utils.cpp_extension still emits Unicode venv
    include/library paths. On affected Windows consoles those paths become
    mojibake and MSVC cannot find `torch/extension.h`.
    """
    if not sys.platform.startswith("win"):
        return None
    torch_pkg = VENV / "Lib" / "site-packages" / "torch"
    torch_include = torch_pkg / "include"
    torch_lib = torch_pkg / "lib"
    header = torch_include / "torch" / "extension.h"
    if not header.exists():
        raise RuntimeError(f"Khong thay torch header: {header}")
    if not torch_lib.exists():
        raise RuntimeError(f"Khong thay torch lib dir: {torch_lib}")

    bridge_root = ascii_build_root()
    include_alias = _mirror_tree_ascii(torch_include, bridge_root / "torch_include")
    lib_alias = _mirror_tree_ascii(torch_lib, bridge_root / "torch_lib")
    api_alias = include_alias / "torch" / "csrc" / "api" / "include"

    # cl.exe always searches INCLUDE and link.exe searches LIB in addition to
    # command-line /I and /LIBPATH entries. Put valid ASCII aliases first, so
    # corrupted Unicode paths generated by cpp_extension no longer matter.
    sep = os.pathsep
    old_include = os.environ.get("INCLUDE", "")
    old_lib = os.environ.get("LIB", "")
    old_path = os.environ.get("PATH", "")
    os.environ["INCLUDE"] = sep.join(
        [str(include_alias), str(api_alias)] + ([old_include] if old_include else [])
    )
    os.environ["LIB"] = sep.join([str(lib_alias)] + ([old_lib] if old_lib else []))
    os.environ["PATH"] = sep.join([str(lib_alias)] + ([old_path] if old_path else []))
    log_line(f"[ASCII-TORCH] include={include_alias}")
    log_line(f"[ASCII-TORCH] api={api_alias}")
    log_line(f"[ASCII-TORCH] lib={lib_alias}")
    return include_alias, lib_alias


def stage_native_source(folder: Path) -> Path:
    """Copy one extension source tree to an ASCII-only staging directory."""
    root = ascii_build_root()
    stage = root / folder.name
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    ignore = shutil.ignore_patterns("build", "dist", "*.egg-info", "*.pyd", "*.so", "__pycache__")
    shutil.copytree(folder, stage, ignore=ignore)
    if not path_is_ascii(stage):
        raise RuntimeError(f"Build staging path van co Unicode: {stage}")
    log_line(f"[ASCII-STAGE] {folder} -> {stage}")
    return stage


def sync_built_binaries(stage: Path, original: Path) -> None:
    """Keep a local copy of built .pyd files next to upstream source as fallback."""
    for binary in stage.rglob("*.pyd"):
        try:
            rel = binary.relative_to(stage)
        except ValueError:
            continue
        # Only copy inplace extension outputs, not transient build-tree duplicates.
        if "build" in rel.parts or "dist" in rel.parts:
            continue
        target = original / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, target)
        log_line(f"[SYNC] {binary.name} -> {target}")


def patch_windows_source() -> list[str]:
    """Apply only known-safe upstream Windows portability fixes when old source is present."""
    changed: list[str] = []
    base = DEST / "hy3dgen" / "texgen" / "custom_rasterizer" / "lib" / "custom_rasterizer_kernel"
    # These exact replacements mirror the Windows portability changes discussed upstream.
    size_replacements = {
        "torch::zeros({seq2pos.size() / 3, 3},": "torch::zeros({static_cast<int64_t>(seq2pos.size() / 3), static_cast<int64_t>(3)},",
        "torch::zeros({seq2pos.size() / 3},": "torch::zeros({static_cast<int64_t>(seq2pos.size() / 3)},",
        "torch::zeros({seq2feat.size() / feat_channel, feat_channel},": "torch::zeros({static_cast<int64_t>(seq2feat.size() / feat_channel), static_cast<int64_t>(feat_channel)},",
        "torch::zeros({grids[i].seq2grid.size(), 9},": "torch::zeros({static_cast<int64_t>(grids[i].seq2grid.size()), static_cast<int64_t>(9)},",
        "torch::zeros({grids[i].seq2evencorner.size()},": "torch::zeros({static_cast<int64_t>(grids[i].seq2evencorner.size())},",
        "torch::zeros({grids[i].seq2oddcorner.size()},": "torch::zeros({static_cast<int64_t>(grids[i].seq2oddcorner.size())},",
        "torch::zeros({grids[i].downsample_seq.size()},": "torch::zeros({static_cast<int64_t>(grids[i].downsample_seq.size())},",
    }
    for name in ("grid_neighbor.cpp", "rasterizer.cpp"):
        path = base / name
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        out = src
        # Windows long is 32-bit; PyTorch int64 tensors require int64_t pointers.
        out = out.replace("data_ptr<long>()", "data_ptr<int64_t>()")
        out = re.sub(r"\blong\s*\*\s*([A-Za-z_]\w*)\s*=\s*([^;]*data_ptr<int64_t>\(\));", r"int64_t* \1 = \2;", out)
        if name == "grid_neighbor.cpp":
            for old, new in size_replacements.items():
                out = out.replace(old, new)
        if out != src:
            backup = path.with_suffix(path.suffix + ".aivf0870.bak")
            if not backup.exists():
                backup.write_text(src, encoding="utf-8")
            path.write_text(out, encoding="utf-8")
            changed.append(name)
    return changed


def clean_build(folder: Path) -> None:
    for item in (folder / "build",):
        if item.exists():
            shutil.rmtree(item, ignore_errors=True)
    for egg in folder.glob("*.egg-info"):
        if egg.is_dir():
            shutil.rmtree(egg, ignore_errors=True)


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    LOG.write_text("AI Video Factory 0.8.7.6 Character HD Paint build log\n", encoding="utf-8")
    python = vpy()
    if not python.exists() or not (RUNTIME / "READY.txt").exists():
        log_line("[LOI] Character HD shape chua cai. Hay chay SETUP_CHARACTER_HD.bat truoc.")
        return 2
    if not DEST.exists():
        log_line("[LOI] Khong thay Hunyuan3D-2 source. Chay SETUP_CHARACTER_HD.bat truoc.")
        return 2

    log_line("================================================")
    log_line(" AI VIDEO FACTORY 0.8.7.6 - CHARACTER HD PAINT")
    log_line(" Windows toolchain + source compatibility build")
    log_line("================================================")
    log_line(f"[ENV] cl={shutil.which('cl') or 'MISSING'}")
    log_line(f"[ENV] nvcc={shutil.which('nvcc') or 'MISSING'}")
    log_line(f"[ENV] CUDA_PATH={os.environ.get('CUDA_PATH','')}")
    if sys.platform.startswith("win"):
        log_line("[WIN-CUDA] NVCC_APPEND_FLAGS += -DUSE_CUDA (PyTorch compiled_autograd C2872 workaround)")
    if shutil.which("cl") is None or shutil.which("nvcc") is None:
        log_line("[LOI] Toolchain chua du. Can ca cl.exe va nvcc.exe trong cung cua so setup.")
        return 4

    changed = patch_windows_source()
    if changed:
        log_line("[PATCH] Da ap dung Windows compatibility: " + ", ".join(changed))
    else:
        log_line("[PATCH] Source da co Windows compatibility hoac khong can sua.")

    run(str(python), "-m", "pip", "install", "--upgrade", "ninja", "pybind11")
    try:
        prepare_ascii_torch_bridge()
    except Exception as exc:
        log_line(f"[LOI] Tao ASCII torch bridge that bai: {type(exc).__name__}: {exc}")
        READY.unlink(missing_ok=True)
        return 5

    parts = [
        DEST / "hy3dgen" / "texgen" / "custom_rasterizer",
        DEST / "hy3dgen" / "texgen" / "differentiable_renderer",
    ]
    ok = True
    failed: list[str] = []
    for folder in parts:
        if not folder.exists():
            log_line("[LOI] Thieu " + str(folder))
            ok = False
            failed.append(folder.name)
            continue
        try:
            # Always stage native builds on Windows. This avoids Ninja corrupting
            # paths such as OneDrive\Máy tính into `M y t nh`.
            build_folder = stage_native_source(folder) if sys.platform.startswith("win") else folder
            clean_build(build_folder)
            code = run(str(python), "setup.py", "build_ext", "--inplace", cwd=build_folder)
            if code == 0:
                code = run(str(python), "setup.py", "install", cwd=build_folder)
            if code == 0 and build_folder != folder:
                sync_built_binaries(build_folder, folder)
        except Exception as exc:
            code = 1
            log_line(f"[LOI] ASCII native build staging that bai: {type(exc).__name__}: {exc}")
        if code != 0:
            ok = False
            failed.append(folder.name)
            log_line("[LOI] Build texture extension that bai: " + folder.name)

    test = (
        "import torch; import custom_rasterizer_kernel; import mesh_processor; "
        "from hy3dgen.texgen import Hunyuan3DPaintPipeline; "
        "print('TEXTURE_NATIVE_OK')"
    )
    if ok and run(str(python), "-c", test) == 0:
        READY.write_text("character_hd_texture_ready_v0873\n", encoding="utf-8")
        log_line("[OK] CHARACTER HD PAINT NATIVE DA SAN SANG.")
        log_line("Mo app va bam TO MAU GLB HIEN CO.")
        return 0

    READY.unlink(missing_ok=True)
    log_line("[LOI] Paint native chua san sang. Shape Character HD van dung binh thuong.")
    if failed:
        log_line("[FAILED] " + ", ".join(failed))
    log_line("[LOG] Gui file data\\runtime_character_hd\\paint_build.log neu can debug tiep.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
