"""Khoa bo cuc tong (master layout lock) TRUOC khi render tung tile.

Ly do can buoc nay: neu moi tile duoc AI sinh doc lap, chi biet "hang xom
la tile nao" qua MO TA CHU (text), khong co gi dam bao pixel o mep tile
thuc su noi lien - day la nguyen nhan chinh gay "tile bi dut". Buoc nay tao
(hoac dung lai anh mau nguoi dung dua vao) DUY NHAT MOT anh bo cuc tong,
va MOI tile sau do deu duoc crop tu chinh anh nay truoc khi AI tinh chinh
chi tiet rieng - dam bao tat ca tile chia se cung 1 nguon bo cuc/hinh hoc.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

MASTER_LAYOUT_SIZE = 1024  # PHAI la 1 trong cac size duoc phep cua LocalImageService
# (xem app/modules/tao_anh_ai/upscale.py::_TARGET_SIZES - vd "1536x1536" se
# raise "Kich thuoc AI anh khong hop le"). Luu y: model SD1.5 cuc bo LUON
# sinh anh o do phan giai goc 512x512 (hoac 640x384) roi finalize_pil() moi
# resize len target_size - nen tang MASTER_LAYOUT_SIZE (vd len 2048x2048)
# KHONG lam anh net hon, chi lam anh to hon (van tu nguon 512x512), vi vay
# khong dang danh doi thoi gian sinh anh de doi len 2048.


def khoa_bo_cuc(*, jobdir: Path, spec: dict, reference_path: Path | None, ai_image_service) -> Path:
    """Tra ve duong dan anh bo cuc tong DA KHOA - dung chung cho MOI tile
    phia sau, bat ke co anh mau nguoi dung hay khong.

    - Co anh mau: dung chinh anh do (chuan hoa ve RGB) - bo cuc da co san.
    - Khong co anh mau: sinh MOT anh DUY NHAT bang AI theo mo ta tong the
      (khac voi tung tile) - day chinh la buoc "khoa" that su, thay vi de
      tung tile tu sinh doc lap khong biet gi ve bo cuc chung.
    """
    out = jobdir / "bo_cuc_tong.png"
    if reference_path is not None:
        with Image.open(reference_path) as im:
            im.convert("RGB").save(out, quality=96)
        return out

    if ai_image_service is None:
        raise RuntimeError("Tạo map từ mô tả cần AI ảnh local đang hoạt động để khóa bố cục tổng trước khi chia tile")

    master_prompt = (
        "Top-down full overview of an ENTIRE seamless game world map, ONE single coherent composition "
        "(not a single tile, the whole map at once). "
        f"{spec.get('prompt') or 'a fantasy game world'}. Style: {spec['style']}; view: {spec['view']}. "
        "Show the complete layout: all roads, rivers, coastlines, biome regions and major landmarks "
        "positioned consistently across the whole map, so every part of it can later be cropped into tiles "
        "that still connect correctly. Do not add labels, text, borders, UI or legends."
    )
    size_txt = f"{MASTER_LAYOUT_SIZE}x{MASTER_LAYOUT_SIZE}"
    raw = ai_image_service.generate(master_prompt, "fantasy", size_txt, "high")
    out.write_bytes(raw)
    return out
