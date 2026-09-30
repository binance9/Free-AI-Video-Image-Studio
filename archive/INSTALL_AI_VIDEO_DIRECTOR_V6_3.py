from __future__ import annotations
from pathlib import Path
import shutil, re, py_compile, sys

ROOT=Path(__file__).resolve().parent
PAYLOAD=ROOT/'_director_v3_payload'
MAIN=ROOT/'app'/'main.py'
INDEX=ROOT/'web'/'index.html'
if not MAIN.is_file() or not INDEX.is_file():
    raise SystemExit('LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory (noi co app/ va web/).')

# Force overwrite module payload so an old V1 cannot survive Windows Extract conflict choices.
for rel in [
    Path('app/modules/ai_video_director'), Path('app/modules/tao_video_ai'),
    Path('web/modules/ai_video_director'), Path('web/modules/tao_video_ai')]:
    src=PAYLOAD/rel; dst=ROOT/rel
    if not src.is_dir(): raise SystemExit(f'LOI: payload thieu {rel}')
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src,dst)

main=MAIN.read_text(encoding='utf-8')
backup=MAIN.with_suffix('.py.before_ai_video_director_v3.bak')
if not backup.exists(): shutil.copy2(MAIN,backup)

director_imp='from app.modules.ai_video_director.api_ai_video_director import router as ai_video_director_router\n'
if 'ai_video_director_router' not in main:
    pos=main.find('def create_app(')
    if pos<0: raise SystemExit('LOI: Khong tim thay create_app trong app/main.py')
    main=main[:pos]+director_imp+'\n'+main[pos:]
video_imp='from app.modules.tao_video_ai.api_tao_video_ai import router as tao_video_ai_router\nfrom app.modules.tao_video_ai import LocalVideoAIService, VideoAIWorkspace, VideoAIJobManager\n'
if 'tao_video_ai_router' not in main:
    pos=main.find('def create_app(')
    if pos<0: raise SystemExit('LOI: Khong tim thay create_app trong app/main.py')
    main=main[:pos]+video_imp+'\n'+main[pos:]
if 'app.state.video_ai_service' not in main:
    marker='    app.state.memory = memory\n'
    if marker not in main: raise SystemExit('LOI: Khong tim thay app.state.memory trong app/main.py')
    block=(
      '    app.state.video_ai_workspace = VideoAIWorkspace(settings.base_dir / "data" / "tao_video_ai")\n'
      '    app.state.video_ai_service = LocalVideoAIService(settings.model_dir / "video", app.state.video_ai_workspace)\n'
      '    app.state.video_ai_jobs = VideoAIJobManager(app.state.video_ai_service, app.state.video_ai_workspace)\n')
    main=main.replace(marker,marker+block,1)
pos=main.find('    app.mount("/static"')
if pos<0: raise SystemExit('LOI: Khong tim thay static mount trong app/main.py')
insert=''
if 'app.include_router(ai_video_director_router)' not in main: insert+='    app.include_router(ai_video_director_router)\n'
if 'app.include_router(tao_video_ai_router)' not in main: insert+='    app.include_router(tao_video_ai_router)\n'
if insert: main=main[:pos]+insert+main[pos:]
MAIN.write_text(main,encoding='utf-8')

idx=INDEX.read_text(encoding='utf-8')
idx_backup=INDEX.with_suffix('.html.before_ai_video_director_v3.bak')
if not idx_backup.exists(): shutil.copy2(INDEX,idx_backup)
refs={
 r'/static/modules/ai_video_director/ai_video_director\.css(?:\?v=[^"\']+)?':'/static/modules/ai_video_director/ai_video_director.css?v=630',
 r'/static/modules/ai_video_director/ai_video_director\.js(?:\?v=[^"\']+)?':'/static/modules/ai_video_director/ai_video_director.js?v=630',
 r'/static/modules/tao_video_ai/tao_video_ai\.css(?:\?v=[^"\']+)?':'/static/modules/tao_video_ai/tao_video_ai.css?v=003',
 r'/static/modules/tao_video_ai/tao_video_ai\.js(?:\?v=[^"\']+)?':'/static/modules/tao_video_ai/tao_video_ai.js?v=003'}
for pat,repl in refs.items(): idx=re.sub(pat,repl,idx)
assets=[
 ('<link rel="stylesheet" href="/static/modules/ai_video_director/ai_video_director.css?v=630">\n','</head>','/static/modules/ai_video_director/ai_video_director.css'),
 ('<link rel="stylesheet" href="/static/modules/tao_video_ai/tao_video_ai.css?v=003">\n','</head>','/static/modules/tao_video_ai/tao_video_ai.css'),
 ('<script src="/static/modules/tao_video_ai/tao_video_ai.js?v=003"></script>\n','</body>','/static/modules/tao_video_ai/tao_video_ai.js'),
 ('<script src="/static/modules/ai_video_director/ai_video_director.js?v=630"></script>\n','</body>','/static/modules/ai_video_director/ai_video_director.js')]
for tag,marker,key in assets:
    if key not in idx: idx=idx.replace(marker,tag+marker,1)
INDEX.write_text(idx,encoding='utf-8')

for p in [ROOT/'app/modules/ai_video_director/service.py',ROOT/'app/modules/ai_video_director/quality.py',ROOT/'app/modules/ai_video_director/auto_producer.py',ROOT/'app/modules/ai_video_director/api_ai_video_director.py',ROOT/'app/modules/tao_video_ai/service.py',ROOT/'app/modules/tao_video_ai/api_tao_video_ai.py',MAIN]:
    py_compile.compile(str(p),doraise=True)

# Assert V6 really replaced V1 on disk.
text=(ROOT/'app/modules/ai_video_director/service.py').read_text(encoding='utf-8')
assert 'preproduction+auto_produce' in text and 'v6.3-live-production-ui' in text
assert 'auto_producer' in (ROOT/'app/modules/ai_video_director/api_ai_video_director.py').read_text(encoding='utf-8')
print('AI VIDEO DIRECTOR V6.3 LIVE PRODUCTION UI INSTALL: PASS')
print('V1 files were force-replaced.')
print('Expected status: phase=preproduction+auto_produce, build=v6.3-live-production-ui')
print('Home UI: Quality First + live ETA + parallel audio prep + no redundant HIGH final re-encode.')
print('Restart bot completely, then Ctrl+F5 browser.')
