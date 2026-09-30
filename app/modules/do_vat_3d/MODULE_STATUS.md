MODULE:
do_vat_3d

MODULE_VERSION:
1.1.0 (Phase 1.6.1 - trước là 1.0.0 ở Phase 1.6; không có VERSION constant riêng trong code, dự án
không dùng quy ước đó ở module khác - version bump ở đây là git tag do-vat-3d-v1-1-complete)

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
2026-08-27 Phase 1.6.1 (đã chạy test thật poly enforcement: category=da, quality=standard,
texture=none, engine=TripoSR - shape thô 127,640 tam giác -> optimized 31,223 (target 32,000,
poly_target_met=true), tổng 29.57s (shape 24.95s + optimize 4.62s). Đã chạy test thật texture=lite
trên cùng ảnh: has_texture=true, texture_error=null, triangle_count giữ nguyên 31,223 sau tô màu,
texture=287.06s, tổng=314.79s (~5.25 phút, trong timeout lite=600s) - xem README_MODULE.md "Kết
quả test thật Phase 1.6.1".

KNOWN_LIMITATIONS (Phase 1.6.1):
- Texture resolution/steps/VRAM-aware runtime degrade CHƯA cấu hình được từ do_vat_3d
  (run_character_hd_paint.py không nhận tham số này; sửa file đó = rủi ro rewrite Hunyuan3D-Paint).
- Model KHÔNG cache trong RAM/GPU giữa các job (kiến trúc subprocess-per-job có sẵn từ trước, chỉ
  cache cấp đĩa/HF cache) - không thêm used_cached_*_model giả vào job.json.
- Timing chỉ tách theo stage (preprocess/shape/optimize/texture/validate/total), KHÔNG tách được
  model_load_seconds riêng (engine chạy như subprocess đen, tách nhỏ hơn cần sửa runner = rewrite).
- Chưa có thumbnail cho asset library (thumbnail_path luôn null hiện tại).
- Map Composer (ban_do_3d) vẫn CHƯA triển khai - nút "DÙNG TRONG MAP" ở UI disabled đúng như yêu
  cầu, không fake chức năng.

RESOLVED trong Phase 1.6.1 (trước đây là KNOWN_LIMITATIONS):
- poly_target giờ được enforce thật cho CẢ TripoSR lẫn character_hd (toi_uu_so_mat + mesh_decimate.py).
- Shared GPU lock (heavy_gpu_job_lock) đã nối vào nhan_vat_3d.job_manager (adapter mỏng).
- Texture stage đã test thật (texture=lite) - xem README_MODULE.md.


HOTFIX 2026-09-01:
- Fixed object module prompt isolation: `do_vat_3d` no longer delegates prompt generation through the generic `Local3DService.from_prompt()` path that could bias concept images toward characters.
- Added `prompt_do_vat.py` object-only prompt builder + human-term guard for strict object categories.
