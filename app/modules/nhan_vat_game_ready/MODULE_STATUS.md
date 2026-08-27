MODULE:
nhan_vat_game_ready

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/nhan_vat_game_ready/api_nhan_vat_game_ready.py

FRONTEND_ENTRY:
web/modules/nhan_vat_game_ready/nhan_vat_game_ready.js

SMOKE_TEST:
pytest -q tests/smoke/test_nhan_vat_game_ready_smoke.py

HEAVY_MODELS:
Blender 4.x (headless, qua subprocess — không phải thư viện Python)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Nếu máy không cài Blender, /api/3d/game-ready/status vẫn trả 200 với installed=false (đã kiểm
tra kỹ trong smoke test, không được coi là lỗi). Frontend JS/CSS mới tách khỏi nhan_vat_3d ở
Phase 1.5 — markup HTML vẫn nằm vật lý trong web/index.html (chưa có templating engine để tách
tiếp). blender_game_ready.py là 1 script liền mạch, chủ động không tách nhỏ thêm (xem README).
