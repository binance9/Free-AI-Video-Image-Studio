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

## Roadmap (kiến trúc dự kiến — CHƯA viết code thật)

**Cấu trúc con dự kiến**:
```
ban_do_3d/
├── dia_hinh        (terrain)
├── duong_di        (road/path)
├── khu_rung        (forest zone)
├── khu_lang        (village zone)
├── dungeon
├── spawn           (vị trí spawn nhân vật/quái)
├── collision       (dữ liệu va chạm)
├── scene_composer  (ghép các phần trên thành 1 scene)
└── export          (xuất scene manifest)
```

**Nguyên tắc bắt buộc — Map phải modular, không được bake chết asset**:
```
MAP
├── TERRAIN
├── ROAD
├── ZONES
├── PROPS
├── SPAWN
├── COLLISION
└── EXPORT
```
Map Composer tương lai phải **dùng asset đã chuẩn hoá từ `do_vat_3d`** (mỗi asset 1 file GLB có
`asset_id` riêng) — **KHÔNG regenerate lại toàn bộ cây/nhà/đá mỗi lần map thay đổi**. Ví dụ:
`tree_oak_01.glb`, `rock_01.glb`, `house_wood_01.glb` — bản đồ chỉ lưu:
```
asset_id, position, rotation, scale
```
Nhờ vậy sửa 1 cây không phải tạo lại cả map.

## 3. Khi lỗi, gửi thư mục nào
```
app/modules/ban_do_3d/
web/modules/ban_do_3d/
```
(Hiện chưa có gì để lỗi — mục này áp dụng từ khi module được triển khai thật.)
