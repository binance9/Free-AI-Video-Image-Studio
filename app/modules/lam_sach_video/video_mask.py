"""Xay dung mask cho vung can xoa (chu/logo/icon).

Mask CHAT (khong lan rong - xem MAX_PADDING) de giu toi da texture nen that
xung quanh, cong voi 1 ban mem (feather alpha) rieng dung de tron mep sau
nay (xem temporal_blend.blend_edges) - KHONG dung blur de "xoa", chi dung
feather de mep khong bi rang cua giua vung da inpaint va anh goc.
"""
from __future__ import annotations

import numpy as np

# "mask khong duoc lan qua rong": gioi han cung padding/feather o muc nho,
# khong cho phep nguoi goi vo tinh truyen gia tri lam mat qua nhieu nen that.
MAX_PADDING = 12
MAX_FEATHER = 10


def build_rect_mask(shape_hw: tuple[int, int], bbox: tuple[int, int, int, int], padding: int = 4) -> np.ndarray:
    """bbox = (x, y, w, h) toa do pixel. Tra ve mask nhi phan uint8 (0/255),
    da clamp trong khung hinh va padding gioi han boi MAX_PADDING."""
    h, w = shape_hw
    x, y, bw, bh = bbox
    pad = max(0, min(MAX_PADDING, int(padding)))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(w, x + bw + pad)
    y1 = min(h, y + bh + pad)
    mask = np.zeros((h, w), dtype=np.uint8)
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = 255
    return mask


def feather_mask(mask: np.ndarray, feather_px: int = 6) -> np.ndarray:
    """Tra ve alpha float32 trong [0,1]: = 1.0 trong mask, giam dan tuyen
    tinh ra 0.0 khi cach bien mask feather_px pixel - dung de blend mep
    (KHONG phai blur noi dung, chi lam mem duong bien khi ghep)."""
    import cv2

    feather_px = max(0, min(MAX_FEATHER, int(feather_px)))
    if feather_px <= 0:
        return (mask > 0).astype(np.float32)
    inv = (255 - mask).astype(np.uint8)
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
    alpha = np.clip(1.0 - dist / float(feather_px), 0.0, 1.0)
    return alpha.astype(np.float32)


def dilate_mask(mask: np.ndarray, pixels: int = 3) -> np.ndarray:
    """Mo rong nhe mask (dung cho sharpen_region - can phu ca vien mep,
    KHONG dung de mo rong vung inpaint chinh)."""
    import cv2

    if pixels <= 0:
        return mask
    kernel = np.ones((max(1, pixels), max(1, pixels)), np.uint8)
    return cv2.dilate(mask, kernel, iterations=1)
