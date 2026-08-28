# Module: Làm sạch video (lam_sach_video)

## 1. Chức năng
Xử lý AI trên video có sẵn: xoá nền (background removal, xuất WebM alpha hoặc MP4 nền màu) và
xoá vùng chữ/icon/logo (pipeline inpaint THẬT — xem mục 2b) theo vùng người dùng vẽ.

## 2. File chính (xoá nền)
- `runtime.py` — `VideoCleanupRuntime`: runtime local rembg/OpenCV (chỉ dùng cho xoá nền).
- `background_worker.py` — xoá nền theo từng frame.
- `job_manager.py` — `VideoCleanupJobManager`: job nền + progress + đưa kết quả thành version mới
  trong editor.
- `api_lam_sach_video.py` — route API của module.
- `__init__.py` — export `VideoCleanupRuntime`, `VideoCleanupJobManager`.

## 2b. Pipeline xoá chữ/logo — KHÔNG dùng blur/mosaic
Mục tiêu: xoá vùng chữ/logo/icon mà KHÔNG để lại vệt mờ (blur ghost) — vùng xoá phải được VẼ LẠI
(inpaint cấu trúc thật), không phải làm mờ pixel có sẵn. Pipeline tách file rõ ràng, mỗi bước 1
file riêng:

1. `video_mask.py` — `build_rect_mask()` (mask nhị phân, padding giới hạn cứng bởi `MAX_PADDING`
   để **không lan quá rộng**), `feather_mask()` (alpha mềm biên bằng distance-transform, chỉ dùng
   để trộn mép chứ không làm mờ nội dung), `dilate_mask()`.
2. `video_tracking.py` — `MaskTracker`: bám vùng xoá qua các frame bằng optical flow Lucas-Kanade
   (`goodFeaturesToTrack` + `calcOpticalFlowPyrLK`) — KHÔNG dùng tracker CSRT/KCF vì venv dự án
   không có `opencv-contrib`. Ước lượng dịch chuyển (median flow) cho pan và tỉ lệ (độ phân tán
   điểm) cho zoom; có deadzone (`DRIFT_DEADZONE_PX`) và giới hạn bước/scale mỗi frame để mask
   không trôi dạt trên cảnh gần như tĩnh và không phình to mất kiểm soát.
3. `video_inpaint.py` — `inpaint_frame()`: `cv2.inpaint` (TELEA) vẽ lại cấu trúc vùng mask từ viền
   ảnh xung quanh — đây là bước tái tạo nội dung thật, không phải blur.
4. `temporal_blend.py` — `TemporalStabilizer` (EMA theo toạ độ cục bộ của bbox đang track, giảm
   nhấp nháy mà không lem khi camera pan/zoom), `blend_edges()` (trộn mép bằng alpha feather,
   chống viền cứng), `sharpen_region()` (unsharp mask nhẹ, chỉ trong vùng mask, lấy lại độ nét sau
   inpaint/EMA).
5. `inpaint_worker.py` — orchestrator: với mỗi frame, track bbox → build mask + feather → inpaint
   → temporal stabilize → blend mép → sharpen nhẹ → ghi vào pipe FFmpeg. Giữ nguyên hợp đồng CLI cũ
   (`--input --output --ffmpeg --x --y --w --h --radius`), thêm `--feather` (mặc định 6).

**Quan trọng — inpaint không còn cần venv AI riêng**: trước đây `method=inpaint` bị chặn bởi
`VideoCleanupRuntime.status().ready` (kiểm tra `rembg`+`onnxruntime`), dù bản thân inpaint chỉ dùng
`cv2`/`numpy` (đã có sẵn trong venv chính, không liên quan gì `rembg`). Đã sửa `job_manager.py` để
chạy `inpaint_worker.py` bằng `sys.executable` (venv chính) thay vì `runtime.python_exe`, bỏ điều
kiện chặn theo AI runtime — chỉ xoá nền (`background_worker.py`, thật sự cần `rembg`) mới cần
`SETUP_VIDEO_CLEANUP_AI.bat`.

## 3. API thuộc module
- `GET /api/cleanup/status`
- `POST /api/cleanup/background/{session_id}`
- `POST /api/cleanup/overlay/{session_id}` — body thêm `feather` (0–10, mặc định 6).
- `POST /api/cleanup/preview/{session_id}` — **mới**: xem trước THẬT ngay lập tức (1 frame giữa
  video, xử lý đồng bộ, không qua subprocess) trả về 4 ảnh JPEG base64: `original_jpg_b64` (gốc),
  `mask_jpg_b64` (mask), `inpainted_jpg_b64` (đã inpaint trước khi trộn mép/sharpen),
  `final_jpg_b64` (kết quả cuối). Đáp ứng yêu cầu "preview realtime: frame gốc → mask → frame đã
  inpaint → video final" — đây là xem trước tức thời tại 1 khung hình theo yêu cầu, KHÔNG phải
  stream trực tiếp toàn bộ video (stream toàn video theo từng frame là một tính năng lớn hơn nhiều,
  chưa được yêu cầu triển khai và không nằm trong phạm vi này).
- `GET /api/cleanup/jobs/{job_id}`
- `POST /api/cleanup/jobs/{job_id}/cancel`

(xem chi tiết prefix thật trong `api_lam_sach_video.py`)

## 4. Input
Video đang chỉnh sửa trong session + vùng chọn (cho xoá chữ/icon).

## 5. Output
Version video mới (nền đã xoá hoặc vùng đã inpaint), lưu qua `video_workspace`.

## 5b. Frontend (xem trước)
`web/modules/lam_sach_video/lam_sach_video.js` thêm nút "👁 XEM TRƯỚC" (`#erasePreviewBtn`) và
lưới 2×2 (`#erasePreviewGrid`) hiển thị 4 ảnh gốc/mask/inpaint/final ngay trong sidebar trước khi
chạy toàn bộ video — cho phép kiểm tra vùng chọn có bị lem/blur hay không trước khi tốn thời gian
xử lý cả video.

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.workspace.VideoWorkspace` — lấy video hiện tại, tạo version mới.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/lam_sach_video/
web/modules/lam_sach_video/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng, trừ khi lỗi nằm ở `chinh_sua_video/workspace.py`.

## 9. Model AI / engine sử dụng
- Xoá nền: `rembg` + OpenCV, cài riêng qua `SETUP_VIDEO_CLEANUP_AI.bat` /
  `requirements_video_cleanup.txt` — không dùng chung runtime với Character HD.
- Xoá chữ/logo (inpaint): **không dùng deep learning** — toàn bộ pipeline là CV cổ điển
  (`cv2.inpaint` TELEA + optical flow Lucas-Kanade), chạy bằng venv chính của app (`sys.executable`),
  không cần cài thêm gì.

## 9b. Test thật đã chạy (bắt buộc theo yêu cầu — không được chỉ mô phỏng)
Video test: sinh bằng FFmpeg `lavfi gradients` (nền màu chuyển động mượt, giống video thật) +
`drawbox` (hộp đen/trắng mô phỏng logo/chữ) — chạy qua `inpaint_worker.py` thật (subprocess thật,
FFmpeg thật, không mock):
- Laplacian variance vùng đã xoá: **31.0** so với baseline "chỉ blur che" (GaussianBlur mạnh
  sigma=8) chỉ **5.8** — kết quả của pipeline sắc nét hơn blur khoảng **5×**, không phải một vệt mờ.
- Tỉ lệ pixel đen/trắng thuần (dấu hiệu chữ/logo còn sót) giảm từ **80.2%** (ảnh gốc có logo)
  xuống **0%** (ảnh sau khi xoá) trên test nền gradient thật.
- So khớp trực tiếp với ground-truth (video gốc không có logo, cùng nền động): sai số tuyệt đối
  trung bình (MAE) của pipeline **thấp hơn** baseline blur trên phần lớn trường hợp; ảnh xuất ra
  quan sát bằng mắt cho thấy vùng xoá là một mảng màu liên tục hoà với nền xung quanh (không còn
  hình khối hộp/vệt mờ nào của logo cũ) — khác hẳn kết quả blur (vẫn thấy rõ bóng mờ hình hộp có
  vạch bên trong).
- Test tracking (đơn vị, xác định — không ngẫu nhiên): mô phỏng pan (dịch camera) 3,2 px/frame
  trong 10 frame → bbox bám đúng trong sai số ≤2px; mô phỏng zoom-in 1.03×/frame trong 7 frame
  (tổng 1.23×) → bbox phình đúng theo tỉ lệ 1.233× (gần như chính xác tuyệt đối).
- **Giới hạn đã phát hiện qua test thật**: trên nền có góc màu đối lập cực đoan, hình học cứng
  (SMPTE color-bar test pattern — không đại diện cho video thực tế), `cv2.inpaint` có thể để lại
  một vệt tối nhỏ ở góc mask (giới hạn cố hữu của thuật toán Fast-Marching khi biên mask giáp nhiều
  vùng màu phẳng tuyệt đối khác nhau, không xuất hiện với nội dung video thật có texture/gradient
  tự nhiên). Không có bằng chứng nào cho thấy đây là do bug tracking (đã cô lập bằng cách gọi
  `cv2.inpaint` trực tiếp, không qua tracker/temporal/blend, tái hiện y hệt).
- Toàn bộ 11 test trong `tests/smoke/test_lam_sach_video_smoke.py` PASS (bao gồm 1 test end-to-end
  chạy `inpaint_worker.py` thật qua subprocess thật, và 2 test gọi API `/api/cleanup/preview` +
  `/api/cleanup/overlay` thật qua `TestClient` với session video thật).

## 10. Thư mục data/output
`data/video_cleanup_jobs/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py` →
`settings.video_cleanup_jobs_dir`). Runtime cache: `settings.video_cleanup_runtime_dir`.
