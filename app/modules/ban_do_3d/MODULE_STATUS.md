MODULE:
ban_do_3d

STATUS:
SCAFFOLD

BACKEND_ENTRY:
(chưa có — chỉ có __init__.py rỗng)

FRONTEND_ENTRY:
(chưa có)

SMOKE_TEST:
pytest -q tests/smoke/test_ban_do_3d_smoke.py

HEAVY_MODELS:
(chưa xác định — roadmap, xem README_MODULE.md)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Chưa triển khai. Roadmap: dia_hinh, duong_di, khu_rung, khu_lang, dungeon, spawn, collision, scene
composer, export. Khi triển khai PHẢI gọi do_vat_3d qua interface/API, không regenerate lại toàn
bộ asset (cây/nhà/đá) mỗi lần map thay đổi — chỉ lưu asset_id + position/rotation/scale.
