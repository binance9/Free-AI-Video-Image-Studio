MODULE:
nhan_vat_2d

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/nhan_vat_2d/api_nhan_vat_2d.py

FRONTEND_ENTRY:
web/modules/nhan_vat_2d/nhan_vat_2d.js

SMOKE_TEST:
pytest -q tests/smoke/test_nhan_vat_2d_smoke.py

HEAVY_MODELS:
Diffusers (SD1.5/SDXL local, biến thể Lightning checkpoint) qua image_runtime.py

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Module lớn nhất (30 file) — nhiều gate/lock tích luỹ qua nhiều version (v6-v13), tên file nội bộ
chưa đổi sang tiếng Việt (Phase 2, sẽ làm sau cùng vì rủi ro cao nhất). Có 4 test pre-existing lỗi
từ trước refactor (LIGHTNING_CKPT thiếu, tham chiếu module app.api.character_2d_standalone đã
chết) — không liên quan tới refactor này, xem baseline pytest.
