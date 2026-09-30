from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "_PATCH_PAYLOAD"
BACKUP = ROOT / f"_BACKUP_DESKTOP_AUTO_FRESH_V6_5_9_{time.strftime('%Y%m%d_%H%M%S')}"
NEW_TARGETS = [
    "AI_VIDEO_FACTORY_DESKTOP.py",
    "START_AI_VIDEO_FACTORY_DESKTOP.bat",
    "app/core/local_freshness.py",
]
MAIN_REL = "app/main.py"
created: list[str] = []


def banner(text: str) -> None:
    print("\n" + "=" * 68)
    print("  " + text)
    print("=" * 68, flush=True)


def backup_file(rel: str) -> None:
    src = ROOT / rel
    if src.is_file():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        created.append(rel)


def rollback(reason: str) -> None:
    banner("ROLLBACK")
    print(reason)
    for rel in [MAIN_REL, *NEW_TARGETS]:
        old = BACKUP / rel
        target = ROOT / rel
        if old.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, target)
        elif rel in created:
            target.unlink(missing_ok=True)
    print("Da khoi phuc source cu.")
    print("Backup:", BACKUP)
    raise SystemExit(10)


def patch_main() -> None:
    path = ROOT / MAIN_REL
    text = path.read_text(encoding="utf-8")

    import_line = "from app.core.local_freshness import install_local_freshness\n"
    if import_line not in text:
        anchor = "from app.core.job_log_broker import job_log_broker\n"
        if anchor not in text:
            raise RuntimeError("Khong tim thay anchor job_log_broker trong app/main.py")
        text = text.replace(anchor, anchor + import_line, 1)

    call = "    install_local_freshness(app)\n"
    if call not in text:
        anchor = "    app = FastAPI(title=settings.app_name, version=settings.version)\n"
        if anchor not in text:
            raise RuntimeError("Khong tim thay anchor FastAPI trong app/main.py")
        text = text.replace(anchor, anchor + call, 1)

    path.write_text(text, encoding="utf-8")


def ps_quote(value: str) -> str:
    return value.replace("'", "''")


def create_shortcut() -> None:
    if os.name != "nt":
        return
    script = ROOT / "AI_VIDEO_FACTORY_DESKTOP.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = pythonw if pythonw.is_file() else Path(sys.executable)
    ps = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$desktop = [Environment]::GetFolderPath('Desktop')",
        "$shortcutPath = Join-Path $desktop 'AI Video Factory.lnk'",
        "$ws = New-Object -ComObject WScript.Shell",
        "$s = $ws.CreateShortcut($shortcutPath)",
        f"$s.TargetPath = '{ps_quote(str(target))}'",
        f"$s.Arguments = '\"{ps_quote(str(script))}\"'",
        f"$s.WorkingDirectory = '{ps_quote(str(ROOT))}'",
        "$s.Description = 'AI Video Factory Desktop'",
        "$s.Save()",
        "Write-Host ('SHORTCUT: ' + $shortcutPath)",
    ])
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        cwd=str(ROOT), check=False,
    )
    if result.returncode != 0:
        print("[CANH BAO] Khong tao duoc Desktop shortcut. Van chay duoc START_AI_VIDEO_FACTORY_DESKTOP.bat")


banner("AI VIDEO FACTORY V6.5.9 - DESKTOP + AUTO FRESH")
if not (ROOT / "app/main.py").is_file() or not (ROOT / "web").is_dir():
    print("[LOI] Hay giai nen TOAN BO ZIP vao thu muc goc ai_video_factory.")
    raise SystemExit(2)
for rel in NEW_TARGETS:
    if not (PAYLOAD / rel).is_file():
        print("[LOI] Thieu payload:", rel)
        raise SystemExit(3)

banner("1/5 - BACKUP")
for rel in [MAIN_REL, *NEW_TARGETS]:
    backup_file(rel)
    print("BACKUP/NEW", rel)

banner("2/5 - INSTALL DESKTOP FILES")
try:
    for rel in NEW_TARGETS:
        source = PAYLOAD / rel
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print("PATCH ", rel)
    patch_main()
    print("PATCH ", MAIN_REL, "(surgical no-cache hook)")
except Exception as exc:
    rollback("Patch that bai: " + str(exc))

banner("3/5 - COMPILE")
try:
    for rel in ("AI_VIDEO_FACTORY_DESKTOP.py", "app/core/local_freshness.py", "app/main.py"):
        py_compile.compile(str(ROOT / rel), doraise=True)
    print("PY_COMPILE: PASS")
except Exception as exc:
    rollback("PY_COMPILE FAIL: " + str(exc))

banner("4/5 - VERIFY")
verify = ROOT / "VERIFY_DESKTOP_AUTO_FRESH_V6_5_9.py"
result = subprocess.run([sys.executable, str(verify)], cwd=str(ROOT), check=False)
if result.returncode != 0:
    rollback("DESKTOP AUTO FRESH VERIFY FAIL")

banner("5/5 - DESKTOP SHORTCUT")
try:
    create_shortcut()
except Exception as exc:
    print("[CANH BAO] Shortcut:", exc)

print("\nDESKTOP AUTO FRESH V6.5.9: PASS")
print("Moi lan mo app:")
print("- neu source/UI da sua va backend cu dang ranh -> tu restart de nap code moi")
print("- neu dang render -> KHONG giet job; danh dau restart pending")
print("- xoa __pycache__ khi can nap source moi")
print("- JS/CSS/HTML localhost dung no-cache de khong bi giao dien cu")
print("- tao shortcut 'AI Video Factory' ngoai Desktop (Windows)")
print("Backup:", BACKUP)
