# Module: Công cụ văn bản (cong_cu_van_ban)

## 1. Chức năng
Catalog các mẫu (preset) chữ/karaoke/phụ đề dùng để dựng layer text trong video editor.
Chỉ là dữ liệu tĩnh, không có xử lý AI.

## 2. File chính
- `catalog.py` — `list_presets()` / `get_preset()`, danh sách preset kiểu chữ.
- `api_cong_cu_van_ban.py` — route `/api/text/presets`.
- `__init__.py` — export `list_presets`.

## 3. API thuộc module
- `GET /api/text/presets`

## 4. Input
Không có (chỉ đọc danh sách tĩnh).

## 5. Output
JSON danh sách preset (id, tên, style) để frontend dựng layer chữ.

## 6. Phụ thuộc module khác
Không phụ thuộc module nào. Ngược lại, `web/modules/phu_de/` (captions) gọi
`window.TextTemplates.getPreset` ở phía frontend để tạo layer phụ đề — đây là dependency
một chiều từ `phu_de` sang module này, không phải ngược lại.

## 7. Khi lỗi, gửi thư mục nào
```
app/modules/cong_cu_van_ban/
web/modules/cong_cu_van_ban/   (khi đã tách frontend)
```

## 8. Không được sửa file ngoài module này nếu chưa thật sự cần
Đúng — module này độc lập hoàn toàn.

## 9. Model AI / engine sử dụng
Không dùng AI.

## 10. Thư mục data/output
Không có — dữ liệu là hằng số Python trong `catalog.py`, không ghi ra `data/`.
