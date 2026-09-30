from pathlib import Path
import shutil, re, py_compile

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "_director_v3_payload"
MAIN = ROOT / "app" / "main.py"
INDEX = ROOT / "web" / "index.html"

if not MAIN.is_file() or not INDEX.is_file():
    raise SystemExit("LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory.")

for rel in [Path("app/modules/ai_video_director"), Path("web/modules/ai_video_director")]:
    src = PAYLOAD / rel
    dst = ROOT / rel
    if not src.is_dir():
        raise SystemExit(f"LOI: payload thieu {rel}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

main = MAIN.read_text(encoding="utf-8")
imp = "from app.modules.ai_video_director.api_ai_video_director import router as ai_video_director_router\n"
if "ai_video_director_router" not in main:
    pos = main.find("def create_app(")
    if pos < 0:
        raise SystemExit("LOI: khong tim thay create_app")
    main = main[:pos] + imp + "\n" + main[pos:]
pos = main.find('    app.mount("/static"')
if pos >= 0 and "app.include_router(ai_video_director_router)" not in main:
    main = main[:pos] + "    app.include_router(ai_video_director_router)\n" + main[pos:]
MAIN.write_text(main, encoding="utf-8")

idx = INDEX.read_text(encoding="utf-8")
idx = re.sub(r'/static/modules/ai_video_director/ai_video_director\.css(?:\?v=[^"\']+)?',
             '/static/modules/ai_video_director/ai_video_director.css?v=650', idx)
idx = re.sub(r'/static/modules/ai_video_director/ai_video_director\.js(?:\?v=[^"\']+)?',
             '/static/modules/ai_video_director/ai_video_director.js?v=650', idx)
INDEX.write_text(idx, encoding="utf-8")

for p in [
    ROOT/"app/modules/ai_video_director/module_router.py",
    ROOT/"app/modules/ai_video_director/service.py",
    ROOT/"app/modules/ai_video_director/auto_producer.py",
    ROOT/"app/modules/ai_video_director/quality.py",
    ROOT/"app/modules/ai_video_director/api_ai_video_director.py",
    MAIN,
]:
    py_compile.compile(str(p), doraise=True)

print("AI VIDEO DIRECTOR V6.5 MODULE ISOLATION INSTALL: PASS")
print("Chi overwrite AI Director.")
print("KHONG sua code ben trong cac module tao anh / 2D / 3D character / 3D object / video / maintenance.")
print("Restart bot roi Ctrl+F5.")
