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
pytest -q tests/test_nhan_vat_game_ready_unit.py

HEAVY_MODELS:
Blender 5.x (headless, qua subprocess — không phải thư viện Python)

LAST_VERIFIED:
2026-08-27 Phase 1.6.2 (đã chạy Blender 5.2.1 LTS thật trên mesh Character HD thật 634,051 tam
giác: rig 18 bone + skin fallback (weight_coverage=1.0) + idle/run/attack_01 có chuyển động thật
(clip_has_motion=true cả 3), validation.ok=true, animation_ok=true - xem README_MODULE.md mục 11)

KNOWN_LIMITATIONS:
Nếu máy không cài Blender, /api/3d/game-ready/status vẫn trả 200 với installed=false (đã kiểm
tra kỹ trong smoke test, không được coi là lỗi). Frontend JS/CSS mới tách khỏi nhan_vat_3d ở
Phase 1.5 — markup HTML vẫn nằm vật lý trong web/index.html (chưa có templating engine để tách
tiếp). blender_game_ready.py là 1 script liền mạch, chủ động không tách nhỏ thêm (xem README).
Phase 1.6.2 thêm: (1) chưa test thật nhánh skin_method="automatic" thành công (mesh test sẵn có
đều rơi vào fallback); (2) không có headless browser test tool trong môi trường này, viewer được
xác nhận bằng node --check + static assertion + suy luận toán học, không phải mở trình duyệt thật.

RESOLVED trong Phase 1.6.2 (trước đây là bug ẩn, KHÔNG được ghi nhận vì không ai validate độc lập):
- Blender's bone-heat automatic weights thất bại ÂM THẦM (không raise exception) trên mesh AI sinh
  ra → export ra GLB có JOINTS_0/WEIGHTS_0 nhưng KHÔNG có skins[] → nhân vật không thể animate dù
  UI báo "đã tạo xương". Đã có verify weight_coverage thật + fallback bắt buộc + validator độc lập
  (validate_game_ready.py) chặn job PASS giả.
