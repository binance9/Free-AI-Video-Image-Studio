MODULE:
do_vat_3d

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/do_vat_3d/api_do_vat_3d.py

FRONTEND_ENTRY:
web/modules/do_vat_3d/do_vat_3d.js

SMOKE_TEST:
pytest -q tests/smoke/test_do_vat_3d_smoke.py
pytest -q tests/test_do_vat_3d_unit.py

HEAVY_MODELS:
TripoSR, Hunyuan3D-2/Character-HD (dùng chung với nhan_vat_3d, chạy trong venv riêng qua
subprocess - không tốn cài đặt thêm)

LAST_VERIFIED:
2026-08-27 (đã chạy test thật thành công: category=da, quality=standard, texture=none,
engine=TripoSR, 29.47s, GLB hợp lệ 129,680 tam giác - xem README_MODULE.md "Kết quả test thật")

KNOWN_LIMITATIONS:
- poly_target trong quality preset CHƯA được enforce thật cho engine TripoSR (chỉ đúng cho
  character_hd) - xem README_MODULE.md phần "Giới hạn đã biết".
- Shared GPU lock (heavy_gpu_job_lock) mới chỉ áp dụng trong do_vat_3d, CHƯA nối vào job manager
  của nhan_vat_3d - 2 module vẫn có thể tranh GPU thật nếu chạy đồng thời.
- Texture stage (colorize_existing) chưa được test thật trong phase này (chỉ test thật nhánh
  shape-only, texture="none") - logic giữ shape khi texture lỗi đã có nhưng chưa verify bằng job
  thật có texture.
- Chưa có thumbnail cho asset library (thumbnail_path luôn null hiện tại).
- Map Composer (ban_do_3d) vẫn CHƯA triển khai - nút "DÙNG TRONG MAP" ở UI disabled đúng như yêu
  cầu, không fake chức năng.
