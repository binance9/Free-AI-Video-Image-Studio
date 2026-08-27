# Module: Bản đồ 3D (ban_do_3d)

## Trạng thái: CHƯA TRIỂN KHAI

Đây là thư mục khung (skeleton) được tạo sẵn theo đúng kiến trúc module độc lập, để khi tính năng
này được xây dựng thì có đúng chỗ chứa — hiện tại **không có code/logic thật nào** ở đây.

## 1. Chức năng dự kiến
Tạo bản đồ 3D cho game: terrain, đường đi (road/path), biome, khu rừng, làng, dungeon, vị trí
spawn, rải vật thể (prop placement), dữ liệu va chạm (collision metadata), ghép scene, xuất bản đồ
(scene manifest).

## 2. Quan hệ dự kiến với module khác
Khi triển khai, `ban_do_3d` sẽ **gọi** `app.modules.do_vat_3d` (qua interface/API, không copy
code) để sinh từng vật thể lẻ (cây, đá, nhà nhỏ...) rồi rải vào bản đồ. Không được nhét logic dựng
mesh của `do_vat_3d` hay `nhan_vat_3d` trực tiếp vào module này.

## 3. Khi lỗi, gửi thư mục nào
```
app/modules/ban_do_3d/
web/modules/ban_do_3d/
```
(Hiện chưa có gì để lỗi — mục này áp dụng từ khi module được triển khai thật.)
