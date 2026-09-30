from pathlib import Path
import shutil, re, sys

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / '_ui_payload' / 'web' / 'modules' / 'ai_video_director'
WEB = ROOT / 'web'
INDEX = WEB / 'index.html'
DST = WEB / 'modules' / 'ai_video_director'

if not INDEX.is_file() or not WEB.is_dir():
    raise SystemExit('LOI: Giai nen ZIP vao THU MUC GOC ai_video_factory (noi co web/index.html).')
if not (PAYLOAD / 'ai_video_director.js').is_file() or not (PAYLOAD / 'ai_video_director.css').is_file():
    raise SystemExit('LOI: payload frontend bi thieu.')

DST.mkdir(parents=True, exist_ok=True)
for name in ['ai_video_director.js','ai_video_director.css']:
    src = PAYLOAD / name
    dst = DST / name
    bak = dst.with_suffix(dst.suffix + '.before_v6_3_1_ui.bak')
    if dst.exists() and not bak.exists():
        shutil.copy2(dst, bak)
    shutil.copy2(src, dst)

idx = INDEX.read_text(encoding='utf-8')
bak = INDEX.with_suffix('.html.before_v6_3_1_ui.bak')
if not bak.exists():
    shutil.copy2(INDEX, bak)
idx = re.sub(r'/static/modules/ai_video_director/ai_video_director\.css(?:\?v=[^"\']+)?',
             '/static/modules/ai_video_director/ai_video_director.css?v=631', idx)
idx = re.sub(r'/static/modules/ai_video_director/ai_video_director\.js(?:\?v=[^"\']+)?',
             '/static/modules/ai_video_director/ai_video_director.js?v=631', idx)
if '/static/modules/ai_video_director/ai_video_director.css' not in idx:
    idx = idx.replace('</head>', '<link rel="stylesheet" href="/static/modules/ai_video_director/ai_video_director.css?v=631">\n</head>', 1)
if '/static/modules/ai_video_director/ai_video_director.js' not in idx:
    idx = idx.replace('</body>', '<script src="/static/modules/ai_video_director/ai_video_director.js?v=631"></script>\n</body>', 1)
INDEX.write_text(idx, encoding='utf-8')

js=(DST/'ai_video_director.js').read_text(encoding='utf-8')
assert 'forceLivePlacement' in js
assert 'findSystemLogTarget' in js
assert "scrollIntoView({block:'nearest'" in js

print('AI VIDEO DIRECTOR V6.3.1 UI-ONLY INSTALL: PASS')
print('CHANGED: web/modules/ai_video_director/ai_video_director.js + .css + index cache version only')
print('NOT TOUCHED: app/, AI planner, prompt contract, SDXL, models, AUTO PRODUCE backend')
print('Restart bot completely, then Ctrl+F5.')
