# Module: Chỉnh sửa ảnh (chinh_sua_anh)

## Trạng thái: CHƯA TRIỂN KHAI

Đây là thư mục khung (skeleton) được tạo sẵn theo đúng kiến trúc module độc lập, để khi tính năng
này được xây dựng thì có đúng chỗ chứa — hiện tại **không có code/logic thật nào** ở đây.

## 1. Chức năng dự kiến
Công cụ chỉnh sửa ảnh không dùng AI sinh mới: crop, resize, xoá nền, thay nền, overlay, thêm
icon/chữ, làm nét, đổi màu, ghép ảnh đơn giản.

## 2. Ghi chú quan trọng
KHÔNG nhét logic sinh ảnh AI (text-to-image) vào đây — phần đó đã có ở
`app.modules.tao_anh_ai`. Module này chỉ chỉnh sửa ảnh có sẵn.

## 3. Khi lỗi, gửi thư mục nào
```
app/modules/chinh_sua_anh/
web/modules/chinh_sua_anh/
```
(Hiện chưa có gì để lỗi — mục này áp dụng từ khi module được triển khai thật.)
