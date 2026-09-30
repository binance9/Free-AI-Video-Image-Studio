from pathlib import Path
import shutil, py_compile
ROOT=Path(__file__).resolve().parent
TARGET=ROOT/'app/modules/ai_video_director'
if not TARGET.is_dir():
    raise SystemExit('LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory.')
for name in ('quality.py','auto_producer.py'):
    src=ROOT/'_fps_patch'/name
    dst=TARGET/name
    if not src.is_file(): raise SystemExit(f'LOI: thieu {src}')
    shutil.copy2(src,dst)
    py_compile.compile(str(dst),doraise=True)
print('V6.5.1 FPS NORMALIZE FIX: PASS')
print('Da sua Director FPS normalize + VIDEO QA. Khong sua AI/model/tao_video_ai.')
print('Restart bot hoan toan roi Ctrl+F5.')
