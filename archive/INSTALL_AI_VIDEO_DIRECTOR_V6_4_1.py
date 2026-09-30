from __future__ import annotations
from pathlib import Path
import shutil, re, py_compile

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / '_director_v3_payload'
MAIN = ROOT / 'app' / 'main.py'
INDEX = ROOT / 'web' / 'index.html'

if not MAIN.is_file() or not INDEX.is_file():
    raise SystemExit('LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory (noi co app/ va web/).')

# V6.4 intentionally updates ONLY AI Director. It does not overwrite AI core,
# model runtime, prompt planner configuration, tao_anh_ai, or tao_video_ai.
for rel in [Path('app/modules/ai_video_director'), Path('web/modules/ai_video_director')]:
    src = PAYLOAD / rel
    dst = ROOT / rel
    if not src.is_dir():
        raise SystemExit(f'LOI: payload thieu {rel}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

main = MAIN.read_text(encoding='utf-8')
backup = MAIN.with_suffix('.py.before_ai_video_director_v641.bak')
if not backup.exists():
    shutil.copy2(MAIN, backup)

director_imp = 'from app.modules.ai_video_director.api_ai_video_director import router as ai_video_director_router\n'
if 'ai_video_director_router' not in main:
    pos = main.find('def create_app(')
    if pos < 0:
        raise SystemExit('LOI: Khong tim thay create_app trong app/main.py')
    main = main[:pos] + director_imp + '\n' + main[pos:]

pos = main.find('    app.mount("/static"')
if pos < 0:
    raise SystemExit('LOI: Khong tim thay static mount trong app/main.py')
if 'app.include_router(ai_video_director_router)' not in main:
    main = main[:pos] + '    app.include_router(ai_video_director_router)\n' + main[pos:]
MAIN.write_text(main, encoding='utf-8')

idx = INDEX.read_text(encoding='utf-8')
idx_backup = INDEX.with_suffix('.html.before_ai_video_director_v641.bak')
if not idx_backup.exists():
    shutil.copy2(INDEX, idx_backup)

refs = {
    r'/static/modules/ai_video_director/ai_video_director\.css(?:\?v=[^"\']+)?': '/static/modules/ai_video_director/ai_video_director.css?v=641',
    r'/static/modules/ai_video_director/ai_video_director\.js(?:\?v=[^"\']+)?': '/static/modules/ai_video_director/ai_video_director.js?v=641',
}
for pat, repl in refs.items():
    idx = re.sub(pat, repl, idx)

assets = [
    ('<link rel="stylesheet" href="/static/modules/ai_video_director/ai_video_director.css?v=641">\n', '</head>', '/static/modules/ai_video_director/ai_video_director.css'),
    ('<script src="/static/modules/ai_video_director/ai_video_director.js?v=641"></script>\n', '</body>', '/static/modules/ai_video_director/ai_video_director.js'),
]
for tag, marker, key in assets:
    if key not in idx:
        idx = idx.replace(marker, tag + marker, 1)
INDEX.write_text(idx, encoding='utf-8')

for p in [
    ROOT/'app/modules/ai_video_director/service.py',
    ROOT/'app/modules/ai_video_director/quality.py',
    ROOT/'app/modules/ai_video_director/auto_producer.py',
    ROOT/'app/modules/ai_video_director/api_ai_video_director.py',
    MAIN,
]:
    py_compile.compile(str(p), doraise=True)

text = (ROOT/'app/modules/ai_video_director/service.py').read_text(encoding='utf-8')
assert 'preproduction+auto_produce' in text
assert 'v6.4.1-character-reference-route-fix' in text
api = (ROOT/'app/modules/ai_video_director/api_ai_video_director.py').read_text(encoding='utf-8')
assert '@router.post("/reference")' in api and '@router.post("/character-reference")' in api
js = (ROOT/'web/modules/ai_video_director/ai_video_director.js').read_text(encoding='utf-8')
assert 'aivdCharacterReference' in js and 'findSystemLogTarget' in js

print('AI VIDEO DIRECTOR V6.4.1 CHARACTER REFERENCE ROUTE FIX INSTALL: PASS')
print('Updated: AI Director only.')
print('Not overwritten: AI core/model/prompt engine/tao_anh_ai/tao_video_ai.')
print('Expected status: build=v6.4.1-character-reference-route-fix')
print('Restart bot completely, then Ctrl+F5 browser.')
