from __future__ import annotations
import shutil
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
PAYLOAD = BASE / "_GA_PATCH_PAYLOAD"
MAIN = BASE / "app" / "main.py"
INDEX = BASE / "web" / "index.html"
REQ = BASE / "requirements.txt"

def die(msg):
    print("[LOI]", msg)
    raise SystemExit(1)

if not MAIN.is_file() or not INDEX.is_file():
    die("Không thấy app/main.py hoặc web/index.html. Giải nén patch vào thư mục gốc AI Video Factory.")

stamp = time.strftime("%Y%m%d_%H%M%S")
backup = BASE / f"_backup_before_ga_owner_{stamp}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(INDEX, backup / "index.html")
if REQ.is_file():
    shutil.copy2(REQ, backup / "requirements.txt")

for src in PAYLOAD.rglob("*"):
    if src.is_file():
        dst = BASE / src.relative_to(PAYLOAD)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

text = MAIN.read_text(encoding="utf-8")
import_line = "from app.modules.ga_owner.api_ga_owner import router as ga_owner_router"
if import_line not in text:
    anchor = "from app.modules.ban_do_3d.api_ban_do_3d import router as ban_do_3d_router"
    if anchor not in text:
        die("Không tìm thấy ban_do_3d_router trong main.py")
    text = text.replace(anchor, anchor + "\n" + import_line, 1)

include_line = "    app.include_router(ga_owner_router)"
if include_line not in text:
    anchor = "    app.include_router(ban_do_3d_router)"
    if anchor not in text:
        die("Không tìm thấy include ban_do_3d_router")
    text = text.replace(anchor, anchor + "\n" + include_line, 1)
MAIN.write_text(text, encoding="utf-8")

html = INDEX.read_text(encoding="utf-8")
css = '<link rel="stylesheet" href="/static/core/ga_owner.css?v=001">'
if css not in html:
    html = html.replace("</head>", css + "\n</head>", 1)

panel = '''
      <section class="ga-owner" id="gaOwner" aria-label="Gà AI Owner">
        <div class="ga-owner-head">
          <div class="ga-owner-avatar">G</div>
          <div class="ga-owner-title"><b>GÀ AI OWNER</b><small id="gaOwnerSub">Đang kiểm tra não...</small></div>
          <span class="ga-owner-state" id="gaOwnerState">● NGỦ</span>
        </div>
        <div class="ga-owner-chat" id="gaOwnerChat"></div>
        <div class="ga-owner-attach" id="gaOwnerAttach"></div>
        <div class="ga-owner-progress" id="gaOwnerProgress">Sẵn sàng.</div>
        <div class="ga-owner-compose">
          <textarea id="gaOwnerInput" placeholder="gà ơi dậy đi..."></textarea>
          <button id="gaOwnerSend" title="Gửi">➤</button>
        </div>
        <div class="ga-owner-tools">
          <button id="gaOwnerAttachBtn">📎 ẢNH</button>
          <button id="gaOwnerVoice">🎤 MIC</button>
          <button id="gaOwnerEnroll">🔐 ĐK GIỌNG</button>
        </div>
        <input class="ga-owner-file" id="gaOwnerFile" type="file" accept="image/png,image/jpeg,image/webp">
      </section>
'''
if 'id="gaOwner"' not in html:
    anchor = "</nav>"
    pos = html.find(anchor)
    if pos < 0:
        die("Không tìm thấy </nav> để chèn Gà")
    pos += len(anchor)
    html = html[:pos] + "\n" + panel + html[pos:]

js = '<script src="/static/core/ga_owner.js?v=001"></script>'
if js not in html:
    html = html.replace("</body>", js + "\n</body>", 1)
INDEX.write_text(html, encoding="utf-8")

if REQ.is_file():
    req = REQ.read_text(encoding="utf-8")
    for dep in ("numpy>=1.26", "python_speech_features>=0.6"):
        if dep.split(">=")[0].lower() not in req.lower():
            req += "\n" + dep
    REQ.write_text(req.rstrip() + "\n", encoding="utf-8")

print("PATCH GÀ: XONG")
print("Backup:", backup)
