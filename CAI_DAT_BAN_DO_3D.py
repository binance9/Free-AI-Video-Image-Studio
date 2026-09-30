from __future__ import annotations
from pathlib import Path
import datetime, re, shutil, sys

ROOT=Path(__file__).resolve().parent
MAIN=ROOT/"app"/"main.py"
INDEX=ROOT/"web"/"index.html"
BACKUP=ROOT/"_backup_before_map_hd_install"/datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def backup(path:Path):
    rel=path.relative_to(ROOT); dst=BACKUP/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)

def patch_main():
    if not MAIN.exists(): raise RuntimeError("Không tìm thấy app/main.py — hãy đặt ZIP đúng thư mục ai_video_factory")
    text=MAIN.read_text(encoding="utf-8")
    if "ban_do_3d_router" not in text:
        backup(MAIN)
        imp="from app.modules.ban_do_3d.api_ban_do_3d import router as ban_do_3d_router\n"
        # insert before first create_app/app definition, after imports
        pos=text.find("\ndef create_app")
        if pos<0: pos=text.find("\napp = FastAPI")
        if pos<0: raise RuntimeError("Không tìm thấy điểm import an toàn trong app/main.py")
        text=text[:pos]+"\n"+imp+text[pos:]
        # Prefer direct include before static mount (works with router loops and modular mains)
        marker='    app.mount("/static"'
        pos=text.find(marker)
        if pos<0: marker="    app.mount('/static'"; pos=text.find(marker)
        if pos>=0:
            text=text[:pos]+"    app.include_router(ban_do_3d_router)\n"+text[pos:]
        else:
            # fallback: before return app inside create_app
            m=re.search(r"\n\s{4}return app\b",text)
            if not m: raise RuntimeError("Không tìm thấy điểm register router an toàn")
            text=text[:m.start()]+"\n    app.include_router(ban_do_3d_router)"+text[m.start():]
        MAIN.write_text(text,encoding="utf-8")
    return "OK"

def patch_index():
    if not INDEX.exists(): raise RuntimeError("Không tìm thấy web/index.html")
    text=INDEX.read_text(encoding="utf-8")
    changed=False
    css='<link rel="stylesheet" href="/static/modules/ban_do_3d/ban_do_3d.css?v=100">'
    js='<script src="/static/modules/ban_do_3d/ban_do_3d.js?v=100"></script>'
    if "modules/ban_do_3d/ban_do_3d.css" not in text:
        if "</head>" not in text: raise RuntimeError("index.html thiếu </head>")
        backup(INDEX); text=text.replace("</head>",f"  {css}\n</head>"); changed=True
    if "modules/ban_do_3d/ban_do_3d.js" not in text:
        if not changed: backup(INDEX)
        if "</body>" not in text: raise RuntimeError("index.html thiếu </body>")
        text=text.replace("</body>",f"  {js}\n</body>"); changed=True
    if changed: INDEX.write_text(text,encoding="utf-8")
    return "OK"

def docs():
    p=ROOT/"DANH_SACH_MODULE.md"
    section='''\n\n## BẢN ĐỒ HD / BAN_DO_3D\nTRẠNG THÁI: ĐANG DÙNG THẬT V1 HD TILE\nBackend: `app/modules/ban_do_3d/`\nFrontend: `web/modules/ban_do_3d/`\nData: `data/ban_do_3d/jobs/`\nTest nhanh: `pytest -q tests/smoke/test_ban_do_3d_hd_tile_smoke.py`\nKhi lỗi gửi: 2 thư mục module map + map_spec.json + manifest_tiles.json + validation.json + nhat_ky_job.json.\n'''
    if p.exists():
        t=p.read_text(encoding="utf-8")
        if "BẢN ĐỒ HD / BAN_DO_3D" not in t: backup(p); p.write_text(t+section,encoding="utf-8")

if __name__=="__main__":
    try:
        print("AI VIDEO FACTORY - CAI DAT BAN DO HD TILE v1.0")
        print("Root:",ROOT)
        print("Backend wiring:",patch_main())
        print("Frontend wiring:",patch_index())
        docs()
        print("\nHOAN TAT. Backup neu co:",BACKUP)
        print("Khoi dong lai bot, Ctrl+F5, sau do bam nut BẢN ĐỒ HD o goc duoi phai.")
    except Exception as e:
        print("\nLOI CAI DAT:",e)
        sys.exit(1)
