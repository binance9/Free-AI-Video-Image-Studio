"""Tien xu ly anh dau vao rieng cho do vat (khac nhan vat).

Tai dung ham chung app.modules.nhan_vat_3d.image_preprocess.prepare_image_for_3d
(xoa nen phang, crop sat silhouette, dua len canvas vuong) - phan nay THUC SU
generic, khong duplicate. Chi khac 1 diem: nhan vat can le xuong duoi de
"chua cho chan" (vertical_bias=0.54, mac dinh cua ham dung chung), con do vat
(cay, nha, cot...) can canh giua binh thuong (vertical_bias=0.5) vi khong co
gia dinh "dung thang co chan" nhu nhan vat.
"""
from __future__ import annotations

from pathlib import Path

from app.modules.nhan_vat_3d.image_preprocess import prepare_image_for_3d

CANVAS_SIZE_MAC_DINH = 1024
VERTICAL_BIAS_DO_VAT = 0.5  # canh giua, khong lech xuong duoi nhu nhan vat


def chuan_hoa_anh_do_vat(src_path: str | Path, out_path: str | Path, *, canvas_size: int = CANVAS_SIZE_MAC_DINH) -> Path:
    """Crop quanh vat the, giu toan bo silhouette (khong mat canh cay / mai nha /
    chan cot), them padding hop ly, dua len canvas vuong trong suot - canh giua."""
    return prepare_image_for_3d(src_path, out_path, canvas_size=canvas_size, vertical_bias=VERTICAL_BIAS_DO_VAT)
