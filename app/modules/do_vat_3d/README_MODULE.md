# Module: Đồ vật 3D (do_vat_3d)

## Trạng thái: CHƯA TRIỂN KHAI

Đây là thư mục khung (skeleton) được tạo sẵn theo đúng kiến trúc module độc lập, để khi tính năng
này được xây dựng thì có đúng chỗ chứa — hiện tại **không có code/logic thật nào** ở đây.

## 1. Chức năng dự kiến
Sinh asset 3D đơn lẻ (không phải cả bản đồ): cây, đá, thùng, rương, hàng rào, cột, nhà nhỏ, đồ
trang trí, weapon/object 3D nếu phù hợp.

## 2. Quan hệ dự kiến với module khác
`app.modules.ban_do_3d` sẽ gọi module này qua interface/API để lấy từng vật thể lẻ khi rải vào bản
đồ. Có thể tái dùng chung backend dựng mesh với `app.modules.nhan_vat_3d` (TripoSR/Hunyuan) qua
import trực tiếp thay vì copy code, nếu khi triển khai thấy hợp lý.

## 3. Khi lỗi, gửi thư mục nào
```
app/modules/do_vat_3d/
web/modules/do_vat_3d/
```
(Hiện chưa có gì để lỗi — mục này áp dụng từ khi module được triển khai thật.)
