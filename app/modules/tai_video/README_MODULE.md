# Module: Tải video (tai_video)

## 1. Chức năng
Tải video công khai (public) từ Facebook qua yt-dlp, chạy nền có job/progress, và import kết quả
thẳng vào video editor.

## 2. File chính
- `downloader.py` — `FacebookVideoDownloader`: validate link Facebook public, chạy yt-dlp.
- `job_manager.py` — `FacebookVideoJobManager`: job nền + progress + import vào editor.
- `api_tai_video.py` — route API của module.
- `__init__.py` — export `FacebookVideoDownloader`, `FacebookVideoJobManager`,
  `FacebookVideoDownloadError`.

## 3. API thuộc module
- `GET /api/facebook-video/status`
- `POST /api/facebook-video/jobs`
- `GET /api/facebook-video/jobs/{job_id}`
- `GET /api/facebook-video/jobs/{job_id}/file`
- `POST /api/facebook-video/jobs/{job_id}/cancel`

## 4. Input
Link video Facebook công khai (không hỗ trợ bypass đăng nhập/cookie riêng tư).

## 5. Output
File video .mp4 tải về, có thể import thẳng vào session editor.

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.workspace.VideoWorkspace` — import video tải về vào session editor.
- `app/core/shared_services.py` (job cancel dùng chung qua `job_control_routes`).

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/tai_video/
web/modules/tai_video/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng, trừ khi lỗi nằm ở `chinh_sua_video/workspace.py` hoặc cơ chế cancel job dùng chung.

## 9. Model AI / engine sử dụng
Không dùng AI — dùng thư viện `yt-dlp`.

## 10. Thư mục data/output
`data/facebook_downloads/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py` →
`settings.facebook_download_dir`).
