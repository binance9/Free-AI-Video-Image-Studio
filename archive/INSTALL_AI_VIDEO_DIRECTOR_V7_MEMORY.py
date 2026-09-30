from pathlib import Path
import shutil, py_compile

ROOT = Path(__file__).resolve().parent
PATCH = ROOT / "_v7_patch"
TARGET = ROOT / "app" / "modules" / "ai_video_director"

if not (ROOT / "app" / "main.py").is_file() or not TARGET.is_dir():
    raise SystemExit("LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory.")

files = ["memory_store.py", "service.py", "api_ai_video_director.py"]
for name in files:
    src = PATCH / name
    if not src.is_file():
        raise SystemExit(f"LOI: patch thieu {name}")
    shutil.copy2(src, TARGET / name)

for name in files:
    py_compile.compile(str(TARGET / name), doraise=True)

print("AI VIDEO DIRECTOR V7 MEMORY INSTALL: PASS")
print("Installed: memory_store.py, service.py, api_ai_video_director.py")
print("Preserved: auto_producer.py, quality.py, module_router.py, AI/model runtimes")
print("Memory path: data/ai_video_director/memory/")
print("Restart bot completely after install.")
