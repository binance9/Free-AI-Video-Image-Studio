# Module: Nhân vật 2D (nhan_vat_2d)

## 1. Chức năng
Pipeline sinh nhân vật 2D game từ prompt hoặc từ ảnh tham chiếu: xây dựng/khoá prompt theo hồ sơ
nhân vật (`CharacterProfile`), giữ nhất quán khuôn mặt/thuộc tính/tham chiếu qua nhiều frame, kiểm
tra chất lượng (mặt/toàn thân/nền), tự sửa lỗi (auto-repair), đổi màu trang phục, xuất sprite.
Đây là module **lớn và nhạy cảm nhất** (30 file) — phần lớn file là các "gate"/"lock" tích luỹ qua
nhiều version (v6 → v13) để giữ nhân vật đúng identity/vũ khí/màu sắc qua các lần sinh lại.

## 2. File chính (nhóm theo vai trò, KHÔNG đổi tên/gộp ở Phase 1 để tránh phá logic đang chạy)
- Điều phối: `service.py` (`Character2DService` — 3 luồng: `create_anchor`, `create_from_reference`,
  `create_action_sheet`), `spec_parser.py`, `command_spec.py`, `character_profile.py`.
- Dựng prompt: `prompt_builder.py`, `direction_builder.py`, `compact_composition.py`.
- Khoá nhất quán: `prompt_lock.py`, `attribute_lock.py`, `reference_lock.py`, `reference_similarity.py`,
  `operation_gate.py`, `consistency.py`.
- Kiểm tra chất lượng: `quality_gate.py`, `face_quality.py`, `fullbody_quality.py`,
  `background_quality.py`, `single_character_quality.py`, `preview_validator.py`, `output_guard.py`,
  `compliance_gate.py`.
- Tự sửa: `auto_repair.py`, `repair_planner.py`, `face_refiner.py`.
- Màu/xuất: `material_recolor.py`, `preserve_refine.py`, `export_gate.py`, `sprite_export.py`.
- Runtime sinh ảnh: `image_runtime.py` (`StandaloneLocalImageService`, pipeline Diffusers).
- Từ ảnh tham chiếu: `from_reference.py`.
- Báo cáo job: `job_report.py`.
- `api_nhan_vat_2d.py` — route API của module.

## 3. API thuộc module
Xem chi tiết trong `api_nhan_vat_2d.py` (prefix route tạo/kiểm tra nhân vật 2D).

## 4. Input
Prompt mô tả nhân vật, hoặc ảnh tham chiếu (từ upload hoặc từ `templates/`).

## 5. Output
Ảnh PNG nhân vật (anchor/action sheet) đã qua toàn bộ quality gate, kèm `job_report`.

## 6. Phụ thuộc module khác
Không phụ thuộc module chức năng khác trực tiếp trong luồng chính. Có handoff sang
`app.modules.nhan_vat_3d` ở tầng frontend (nút "dùng ảnh này để tạo 3D") — không phải phụ thuộc
Python trực tiếp.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/nhan_vat_2d/
web/modules/nhan_vat_2d/   (khi đã tách frontend)
```
Không cần gửi `nhan_vat_3d/`, `chinh_sua_video/` nếu lỗi không liên quan.

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng — đặc biệt module này có rất nhiều gate tinh chỉnh qua nhiều version, sửa nhầm file dễ làm
hỏng kết quả đã ổn định.

## 9. Model AI / engine sử dụng
Diffusers (Stable Diffusion/SDXL local, có biến thể Lightning checkpoint), chạy qua
`image_runtime.py`.

## 10. Thư mục data/output
`data/character_2d_addon/` (**giữ nguyên tên thư mục vật lý cũ**, xem `app/main.py`:
`Character2DService(root=settings.base_dir / "data" / "character_2d_addon")` — chưa đổi tên theo
quyết định giữ nguyên `data/` ở Phase 1).

## Ghi chú Phase 2 (chưa làm ở lần refactor này)
30 file trong module này vẫn giữ tên tiếng Anh gốc (service.py, image_runtime.py, ...) — việc đổi
sang tên tiếng Việt mô tả đúng nhiệm vụ sẽ làm ở Phase 2, từng file một, để giảm rủi ro cho module
nhạy cảm nhất trong dự án.
