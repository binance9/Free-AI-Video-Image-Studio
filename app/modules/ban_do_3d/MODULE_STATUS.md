MODULE: ban_do_3d
STATUS: ACTIVE_V1_1_HD_TILE
BACKEND_ENTRY: app/modules/ban_do_3d/api_ban_do_3d.py
FRONTEND_ENTRY: web/modules/ban_do_3d/ban_do_3d.js (dùng chung #stage/#ai3dStageViewer sibling
  #mapHdStageViewer, KHÔNG còn modal riêng)
SMOKE_TEST:
  pytest -q tests/smoke/test_ban_do_3d_smoke.py
  pytest -q tests/smoke/test_ban_do_3d_hd_tile_smoke.py
KNOWN_LIMITATIONS: V1 tạo bản đồ HD dạng tile 2D + deep zoom; terrain GLB/heightmap và placement
3D runtime sẽ nối ở phase sau (dat_do_vat.py đã có contract toạ độ).

LAST_VERIFIED (v1.1.0, test thật bằng LocalImageService local, prompt "thành chính ở giữa, rừng
phía tây, sông chảy xuyên map, bờ biển phía đông", quality=lite, 4 tile 1024px):
- TRƯỚC fix (mỗi tile AI sinh độc lập, không khóa bố cục, ghép cạnh-đối-cạnh không blend):
  sharpness_score=1.0, tile_border_score=0.763, overall_score=0.8934, 32.1s.
- SAU fix (khóa bố cục tổng + mọi tile crop từ cùng 1 nguồn + ghép overlap-blend thật):
  sharpness_score=0.9458, tile_border_score=0.794, overall_score=0.8775, dims 1952×1952
  (không còn là 2048×2048 "dán cạnh" ảo — phản ánh đúng hình học có overlap), 199.7s.
- Kết quả: tile_border_score (chỉ số continuity trực tiếp) CẢI THIỆN (0.763→0.794 ở lần đo cuối,
  đã thấy tới 0.805 ở lần đo trước đó cùng cấu hình — dao động do AI sinh ảnh có ngẫu nhiên, không
  cố định seed). sharpness dao động run-to-run (đã thấy 0.7388–1.0 tuỳ lần) vì cùng lý do, không
  phải hồi quy hệ thống. Job chậm hơn đáng kể (32s→200s cho "lite") vì giờ luôn tinh chỉnh AI từng
  tile trên nền đã khóa (trước đây "lite" gọi AI generate() độc lập nhanh nhưng KHÔNG liền mạch).
- Route/UI: GET /api/ban-do-3d/status, /static/modules/ban_do_3d/{ban_do_3d.js,ban_do_3d.css} đều
  200 qua TestClient thật lẫn `uvicorn` process thật.

KNOWN_LIMITATIONS (mới, do đo thật phát hiện):
- "Nhẹ" (lite) không còn nhanh như bản cài gốc (32s→~200s cho 4 tile) vì luôn tinh chỉnh AI từng
  tile để giữ chi tiết (tắt tinh chỉnh cho "lite" đã thử và làm ẢNH MỜ HƠN, không phải nhanh hơn mà
  tốt hơn — xem comment trong cau_hinh_ban_do.py). Nếu cần "lite" thật sự nhanh ở phase sau, cần
  cách tiếp cận khác (vd giảm số tile thay vì bỏ AI refine).
- LocalImageService (app.modules.tao_anh_ai) luôn sinh ảnh SD1.5 ở độ phân giải gốc 512×512 (hoặc
  640×384) bất kể "size" yêu cầu — size chỉ quyết định kích thước resize cuối cùng
  (xem app/modules/tao_anh_ai/upscale.py). Vì vậy tăng MASTER_LAYOUT_SIZE không giúp nét hơn, chỉ
  làm ảnh to hơn từ cùng nguồn 512×512 — KHÔNG nên tăng lên 2048 mà không cân nhắc chi phí thời gian
  đổi lại không có gì.
- Chưa test thật với ảnh mẫu người dùng tải lên (chỉ test nhánh sinh từ prompt/mô tả) và chưa test
  quality=standard/final thật (chỉ lite, để giữ thời gian test hợp lý) — logic 2 nhánh giờ dùng
  chung code path với nhánh đã test (crop_reference_tile từ bo_cuc_tong), rủi ro thấp nhưng chưa có
  bằng chứng thật riêng cho chúng.
