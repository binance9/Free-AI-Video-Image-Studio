# Module: Nhân vật Game Ready (nhan_vat_game_ready)

## 1. Chức năng
Hậu xử lý mesh 3D đã dựng xong (từ `nhan_vat_3d`) thành asset "game-ready": tối ưu mesh
(decimate), dựng khung xương (rig/armature), gán trọng số da (skin weights), tạo animation
placeholder (idle/run/attack...), xuất GLB game-ready. Chạy qua Blender headless (subprocess).

## 2. File chính
- `blender_game_ready.py` — script chạy bằng `blender --python` (không import trực tiếp, chạy như
  subprocess riêng): import GLB → optimize mesh → dựng rig → auto-skin → bake animation → export.
  Đây là một pipeline liền mạch, KHÔNG tách nhỏ thêm dù trông như nhiều trách nhiệm — vì nó là 1
  entry point subprocess duy nhất, tách sẽ tốn chi phí hơn lợi ích.
- `service.py` — `GameReady3DService`: gọi Blender headless, quản lý input/output.
- `jobs.py` — `GameReadyJobManager`: job nền + progress.
- `api_nhan_vat_game_ready.py` — route API của module.

## 3. API thuộc module
Xem chi tiết trong `api_nhan_vat_game_ready.py` (tạo job game-ready từ GLB có sẵn, theo dõi job,
tải kết quả).

## 4. Input
File GLB đã dựng xong (thường là output của `nhan_vat_3d`).

## 5. Output
File `*_game_ready.glb` (đã optimize, có rig + animation placeholder).

## 6. Phụ thuộc module khác
Nhận input là GLB path — không import trực tiếp code của `nhan_vat_3d`, chỉ nhận đường dẫn file
(qua `Model3DWorkspace` được truyền vào từ `main.py`). Đây là ranh giới rõ ràng: **không được**
nhét logic dựng mesh của `nhan_vat_3d` vào module này.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/nhan_vat_game_ready/
web/modules/nhan_vat_game_ready/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng.

## 9. Model AI / engine sử dụng
Không dùng AI — dùng Blender headless (`blender --python blender_game_ready.py`) để rig/animate.

## 10. Thư mục data/output
Dùng chung `data/3d_assets/_game_ready/` qua `Model3DWorkspace` của module `nhan_vat_3d` (xem
`app/core/config.py` → `settings.model_3d_dir / "_game_ready"`).
