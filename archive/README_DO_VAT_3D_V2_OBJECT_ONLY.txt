DO_VAT_3D_V2_OBJECT_ONLY_RTX5060TI

Mục tiêu:
- Chỉ sửa module app/modules/do_vat_3d
- Không đụng vào tao_anh_ai, nhan_vat_2d, nhan_vat_3d, AI Director
- Fix lỗi tạo ĐỒ VẬT 3D nhưng concept/pipeline bị lệch sang NHÂN VẬT

File đã sửa:
- app/modules/do_vat_3d/dich_vu_do_vat_3d.py
- app/modules/do_vat_3d/quan_ly_job.py
- app/modules/do_vat_3d/prompt_do_vat.py   (mới)
- app/modules/do_vat_3d/README_MODULE.md
- app/modules/do_vat_3d/MODULE_STATUS.md

Cách dùng:
1) Giải nén đè vào root dự án AI Video Factory.
2) Restart backend/app.
3) Test lại Đồ vật 3D với prompt kiểu: "bụi hoa vàng", "cây thông thấp", "rương gỗ fantasy".

Kỳ vọng sau fix:
- do_vat_3d từ prompt sẽ tạo concept 2D object-only, không còn append "single full body character".
- Các category object nghiêm ngặt sẽ chặn prompt có từ khóa người/nhân vật.
- Giảm cảnh báo CLIP truncated do prompt ngắn hơn.
