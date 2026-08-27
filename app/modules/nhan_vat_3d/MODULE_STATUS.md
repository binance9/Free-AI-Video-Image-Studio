MODULE:
nhan_vat_3d

STATUS:
ACTIVE

BACKEND_ENTRY:
app/modules/nhan_vat_3d/api_nhan_vat_3d.py

FRONTEND_ENTRY:
web/modules/nhan_vat_3d/nhan_vat_3d.js (+ ai_3d_viewer.js, ai_3d_presets.js)

SMOKE_TEST:
pytest -q tests/smoke/test_nhan_vat_3d_smoke.py

HEAVY_MODELS:
TripoSR, Hunyuan3D-2 / Character-HD (Hunyuan3D-2mini) — chạy trong venv riêng, không load vào
tiến trình FastAPI chính

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
character_hd_backend.py / triposr_backend.py tự dựng đường dẫn subprocess bằng chuỗi
"app"/"modules"/"nhan_vat_3d"/... — PHẢI sửa cùng lúc nếu đổi tên file ở Phase 2 (không phải
import Python nên grep import thường bỏ sót; đã có bài học thực tế từ lam_sach_video/runtime.py).
Không chứa logic rig/animation/Game Ready (đã tách sang nhan_vat_game_ready ở Phase 1.5).
1 test pre-existing lỗi vì thiếu thư viện trimesh trong môi trường test.
