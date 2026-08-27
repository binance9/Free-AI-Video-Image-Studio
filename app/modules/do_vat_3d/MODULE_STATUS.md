MODULE:
do_vat_3d

STATUS:
SCAFFOLD

BACKEND_ENTRY:
(chưa có — chỉ có __init__.py rỗng)

FRONTEND_ENTRY:
(chưa có)

SMOKE_TEST:
pytest -q tests/smoke/test_do_vat_3d_smoke.py

HEAVY_MODELS:
(chưa xác định — roadmap, xem README_MODULE.md)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Chưa triển khai. Roadmap nhóm asset: cay, da, co_bui, ruong, thung, hang_rao, cot, den, nha_nho,
cong, tuong, props_trang_tri. Output tương lai dạng *.glb đơn lẻ (tree.glb, rock.glb...). Sẽ được
ban_do_3d gọi qua interface/API, không copy code.
