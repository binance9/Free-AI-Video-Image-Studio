# Module: Nhân vật 3D (nhan_vat_3d)

## 1. Chức năng
Chuyển prompt/ảnh nhân vật 2D thành mesh 3D (GLB), qua nhiều backend local có thể thay thế nhau
(TripoSR, Hunyuan3D, Character-HD + biến thể paint), kèm tối ưu mesh, xuất GLB có texture, và
xuất video turntable preview.

## 2. File chính
- `service.py` — `Local3DService`: điều phối prompt/ảnh → backend.
- `triposr_backend.py` — backend mặc định TripoSR (chạy qua venv riêng bằng subprocess).
- `hunyuan_backend.py` — adapter backend Hunyuan3D chất lượng cao.
- `character_hd_backend.py`, `run_character_hd.py`, `run_character_hd_paint.py` — backend
  Character-HD (Hunyuan3D-2mini) + biến thể tô màu lại mesh có sẵn.
- `image_preprocess.py` — tiền xử lý ảnh đầu vào cho 3D.
- `mesh_finish.py`, `mesh_optimize_light.py`, `mesh_optimize_profiles.py` — hậu xử lý mesh.
- `textured_glb_export.py` — xuất GLB có texture (cần thư viện `trimesh`).
- `texture_cuda_patch.py` — patch CUDA cho texture trên Windows.
- `windows_path_staging.py` — xử lý đường dẫn an toàn trên Windows (ASCII staging).
- `turntable_video.py` — xuất video turntable preview (dùng `chinh_sua_video.ffmpeg_tools`).
- `workspace.py` — `Model3DWorkspace`: lưu GLB/preview riêng biệt.
- `job_manager.py` — `Model3DJobManager`: job nền + progress + cancel.
- `api_nhan_vat_3d.py` — route API của module.

## 3. API thuộc module
Xem chi tiết trong `api_nhan_vat_3d.py` (tạo job 3D từ ảnh/prompt, theo dõi job, huỷ job, tải
model/preview).

## 4. Input
Ảnh nhân vật (thường là output của `nhan_vat_2d`) hoặc prompt text.

## 5. Output
File GLB (có texture) + video preview turntable.

## 6. Phụ thuộc module khác
- `app.modules.chinh_sua_video.ffmpeg_tools` — xuất video turntable.
- `app.modules.tao_anh_ai` (qua `Local3DService`, tham số `ai_image_service`) — sinh ảnh concept
  từ prompt trước khi dựng 3D nếu không có ảnh đầu vào.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/nhan_vat_3d/
web/modules/nhan_vat_3d/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng. **Lưu ý đặc biệt**: `character_hd_backend.py` và `triposr_backend.py` tự dựng đường dẫn tới
`run_character_hd.py`, `run_character_hd_paint.py`, `textured_glb_export.py`, `mesh_finish.py`
bằng chuỗi `"app"/"modules"/"nhan_vat_3d"/...` để gọi subprocess — nếu đổi tên các file này ở
Phase 2, PHẢI sửa các đường dẫn chuỗi này cùng lúc (không phải import Python nên grep import
thường sẽ bỏ sót).

## 9. Model AI / engine sử dụng
TripoSR, Hunyuan3D-2 (Character-HD = Hunyuan3D-2mini), chạy trong venv riêng (`data/runtime3d/`,
`data/runtime_character_hd/`) — không chạy chung tiến trình FastAPI để tránh xung đột GPU/torch.

## 10. Thư mục data/output
`data/3d_assets/` (workspace GLB/preview), `data/models/3d/` (model cache), `data/runtime3d/`,
`data/runtime_character_hd/` (venv riêng) — giữ nguyên tên thư mục vật lý cũ.
