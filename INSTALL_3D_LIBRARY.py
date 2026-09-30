from __future__ import annotations

import datetime
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "_3d_library_payload"
MAIN = ROOT / "app" / "main.py"
INDEX = ROOT / "web" / "index.html"
BACKUP = ROOT / "_backup_before_3d_library" / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path):
    rel = path.relative_to(ROOT)
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)


def copy_payload():
    for src in PAYLOAD.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(PAYLOAD)
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def patch_main():
    if not MAIN.exists():
        raise RuntimeError("Không tìm thấy app/main.py — hãy giải nén ZIP đúng thư mục ai_video_factory")
    text = MAIN.read_text(encoding="utf-8")
    original = text

    if "model_3d_library_router" not in text:
        anchor = "from app.api.game_ready_3d_routes import router as game_ready_3d_router\n"
        if anchor in text:
            text = text.replace(anchor, anchor + "from app.api.model_3d_library_routes import router as model_3d_library_router\n", 1)
        else:
            pos = text.find("\nfrom app.core.config import settings")
            if pos < 0:
                raise RuntimeError("Không tìm được vị trí import router 3D Library an toàn")
            text = text[:pos] + "\nfrom app.api.model_3d_library_routes import router as model_3d_library_router" + text[pos:]

    if "from app.modules.model_3d_library import Model3DLibrary" not in text:
        anchor = "from app.modules.model_3d_game_ready import GameReady3DService, GameReadyJobManager\n"
        if anchor in text:
            text = text.replace(anchor, anchor + "from app.modules.model_3d_library import Model3DLibrary\n", 1)
        else:
            pos = text.find("\nfrom app.storage.database import Database")
            if pos < 0:
                raise RuntimeError("Không tìm được vị trí import Model3DLibrary an toàn")
            text = text[:pos] + "\nfrom app.modules.model_3d_library import Model3DLibrary" + text[pos:]

    if "app.state.model_3d_library = Model3DLibrary(" not in text:
        anchor = "    app.state.game_ready_3d_jobs = GameReadyJobManager(app.state.game_ready_3d_service, app.state.model_3d_workspace)\n"
        if anchor not in text:
            raise RuntimeError("Không tìm được điểm khởi tạo Game Ready 3D để gắn thư viện")
        text = text.replace(anchor, anchor + '    app.state.model_3d_library = Model3DLibrary(settings.base_dir / "data" / "3d_library", app.state.model_3d_workspace)\n', 1)

    if "app.include_router(model_3d_library_router)" not in text:
        marker = '    app.mount("/static"'
        pos = text.find(marker)
        if pos < 0:
            marker = "    app.mount('/static'"
            pos = text.find(marker)
        if pos < 0:
            raise RuntimeError("Không tìm được app.mount('/static') để register 3D Library")
        text = text[:pos] + "    app.include_router(model_3d_library_router)\n" + text[pos:]

    if text != original:
        backup(MAIN)
        MAIN.write_text(text, encoding="utf-8")
    return "OK"


def patch_index():
    if not INDEX.exists():
        raise RuntimeError("Không tìm thấy web/index.html")
    text = INDEX.read_text(encoding="utf-8")
    if "ai_3d_library.js" in text:
        return "OK (đã có)"
    script = '<script src="/static/js/ai_3d_library.js?v=08934lib1"></script>'
    anchor = '<script src="/static/js/character_2d.js'
    pos = text.find(anchor)
    if pos >= 0:
        text = text[:pos] + script + "\n" + text[pos:]
    elif "</body>" in text:
        text = text.replace("</body>", "  " + script + "\n</body>", 1)
    else:
        raise RuntimeError("index.html thiếu </body>")
    backup(INDEX)
    INDEX.write_text(text, encoding="utf-8")
    return "OK"


def verify():
    checks = {
        "backend service": ROOT / "app" / "modules" / "model_3d_library.py",
        "backend route": ROOT / "app" / "api" / "model_3d_library_routes.py",
        "frontend": ROOT / "web" / "js" / "ai_3d_library.js",
    }
    missing = [name for name, path in checks.items() if not path.exists()]
    if missing:
        raise RuntimeError("Thiếu file sau cài: " + ", ".join(missing))
    main = MAIN.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    if "app.include_router(model_3d_library_router)" not in main or "Model3DLibrary" not in main:
        raise RuntimeError("main.py chưa được gắn 3D Library hoàn chỉnh")
    if "ai_3d_library.js" not in index:
        raise RuntimeError("index.html chưa nạp frontend 3D Library")
    return "PASS"


if __name__ == "__main__":
    try:
        print("AI VIDEO FACTORY - 3D LIBRARY SAFE ADDON")
        print("Root:", ROOT)
        copy_payload()
        print("Backend wiring:", patch_main())
        print("Frontend wiring:", patch_index())
        print("Verify:", verify())
        print("\nHOAN TAT.")
        print("- Khoi dong lai bot")
        print("- Ctrl+F5")
        print("- Vao AI 3D Studio -> THU VIEN 3D")
        print("- Co nut LUU MODEL DANG XEM / MO TEST / XOA")
        print("Backup neu co:", BACKUP)
    except Exception as exc:
        print("\nLOI CAI DAT:", exc)
        sys.exit(1)
