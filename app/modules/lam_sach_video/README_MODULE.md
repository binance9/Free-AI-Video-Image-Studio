# Module: Làm sạch video (lam_sach_video)

## 1. Chức năng
Xử lý AI trên video có sẵn: xoá nền (background removal, xuất WebM alpha hoặc MP4 nền màu) và
xoá vùng chữ/icon cố định (inpaint bằng OpenCV) theo vùng người dùng vẽ.

## 2. File chính
- `runtime.py` — `VideoCleanupRuntime`: runtime local rembg/OpenCV, không trộn với Character HD.
- `background_worker.py` — xoá nền theo từng frame.
- `inpaint_worker.py` — xoá vùng chữ/icon cố định theo vùng chọn.
- `job_manager.py` — `VideoCleanupJobManager`: job nền + progress + đưa kết quả thành version mới
  trong editor.
- `api_lam_sach_video.py` — route API của module.
- `__init__.py` — export `VideoCleanupRuntime`, `VideoCleanupJobManager`.

## 3. API thuộc module
- `GET /api/cleanup/status`
- `POST /api/cleanup/background`
- `POST /api/cleanup/overlay`
- `GET /api/cleanup/jobs/{job_id}`
- `POST /api/cleanup/jobs/{job_id}/cancel`

(xem chi tiết prefix thật trong `api_lam_sach_video.py`)

## 4. Input
Video đang chỉnh sửa trong session + vùng chọn (cho xoá chữ/icon).

## 5. Output
Version video mới (nền đã xoá hoặc vùng đã inpaint), lưu qua `video_workspace`.

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
`rembg` (xoá nền) + OpenCV (inpaint), cài riêng qua `SETUP_VIDEO_CLEANUP_AI.bat` /
`requirements_video_cleanup.txt` — không dùng chung runtime với Character HD.

## 10. Thư mục data/output
`data/video_cleanup_jobs/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py` →
`settings.video_cleanup_jobs_dir`). Runtime cache: `settings.video_cleanup_runtime_dir`.
