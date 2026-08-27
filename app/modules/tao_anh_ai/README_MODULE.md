# Module: Tạo ảnh AI (tao_anh_ai)

## 1. Chức năng
Sinh ảnh AI local từ prompt (text-to-image) hoặc từ ảnh tham chiếu (image-to-image/edit), có
upscale, chạy nền qua job queue, và import thẳng ảnh vào video editor làm asset.

## 2. File chính
- `service.py` — `LocalImageService`: chạy pipeline Diffusers sinh/sửa ảnh.
- `upscale.py` — tính kích thước sinh ảnh/đích, upscale hậu kỳ.
- `workspace.py` — `AiImageWorkspace`: lưu ảnh đã sinh.
- `job_manager.py` — `AiImageJobManager`: job nền generate/edit + progress + cancel.
- `api_tao_anh_ai.py` — route API của module.
- `__init__.py` — export `AiImageWorkspace`, `LocalImageService`, `AiImageJobManager`.

## 3. API thuộc module
- `POST /api/ai-image/generate`, `POST /api/ai-image/edit`
- `GET /api/ai-image/{image_id}`
- `POST /api/ai-image/jobs/generate`, `POST /api/ai-image/jobs/edit`
- `GET /api/ai-image/jobs/{job_id}`, `POST /api/ai-image/jobs/{job_id}/cancel`
- `POST /api/editor/{session_id}/asset-from-ai/{image_id}`

## 4. Input
Prompt text, tuỳ chọn style/size/quality, hoặc ảnh tham chiếu (PNG/JPG/WebP).

## 5. Output
Ảnh PNG đã sinh/sửa, có thể import vào session video editor làm asset.

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.workspace.VideoWorkspace` — import ảnh AI vào session
  (`import_ai_image`).

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/tao_anh_ai/
web/modules/tao_anh_ai/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng, trừ khi lỗi nằm ở `chinh_sua_video/workspace.py`.

## 9. Model AI / engine sử dụng
Diffusers (Stable Diffusion local, xem `app/core/config.py` → `settings.image_model`), cache
model tại `data/models/image/`.

## 10. Thư mục data/output
`data/ai_images/` (giữ nguyên tên thư mục vật lý cũ, xem `app/core/config.py` →
`settings.ai_image_dir`).
