MODULE:
chinh_sua_video

STATUS:
CORE DÙNG CHUNG

BACKEND_ENTRY:
app/modules/chinh_sua_video/api_chinh_sua_video.py

FRONTEND_ENTRY:
web/core/app.js (logic editor chính) + web/modules/chinh_sua_video/emoji_picker.js

SMOKE_TEST:
pytest -q tests/smoke/test_chinh_sua_video_smoke.py

HEAVY_MODELS:
Không có (dùng ffmpeg trực tiếp)

LAST_VERIFIED:
2026-08-27

KNOWN_LIMITATIONS:
Module dùng chung nhiều nhất trong dự án — ffmpeg_tools.py/probe.py/errors.py/workspace.py bị
import trực tiếp bởi am_nhac, phu_de, tai_video, lam_sach_video, tao_anh_ai, nhan_vat_3d. Sửa các
file này ảnh hưởng nhiều module khác, cần đặc biệt cẩn trọng.

2026-08-31: chức năng CẮT (cut) đã tách ra module độc lập app/modules/cat_video/ (đã có bản copy
riêng ffmpeg_tools.py/probe.py/errors.py, không import từ module này). Xem
app/modules/cat_video/MODULE_STATUS.md.
