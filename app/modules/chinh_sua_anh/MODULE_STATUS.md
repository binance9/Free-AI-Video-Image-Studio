MODULE:
chinh_sua_anh

STATUS:
SCAFFOLD

BACKEND_ENTRY:
(chưa có — chỉ có __init__.py rỗng)

FRONTEND_ENTRY:
(chưa có)

SMOKE_TEST:
pytest -q tests/smoke/test_chinh_sua_anh_smoke.py

HEAVY_MODELS:
Không có (dự kiến không dùng AI, chỉ chỉnh sửa ảnh có sẵn — xem README_MODULE.md)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Chưa triển khai. Không được nhét logic sinh ảnh AI (text-to-image) vào đây khi triển khai — phần
đó đã có ở app.modules.tao_anh_ai.
