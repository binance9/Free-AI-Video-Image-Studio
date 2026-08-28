"""Video inpainting THAT cho tung frame (khong phai blur/mosaic).

cv2.inpaint "ve lai" cau truc vung mask dua tren vien anh xung quanh (thuat
toan TELEA hoac Navier-Stokes) - day la inpainting cau truc thuc su: pixel
trong vung mask duoc thay the boi noi dung tai tao, khac han blur (chi lam
nhoe/tron pixel co san, khong tai tao noi dung moi).
"""
from __future__ import annotations

import cv2
import numpy as np

_METHODS = {"telea": cv2.INPAINT_TELEA, "ns": cv2.INPAINT_NS}


def inpaint_frame(frame_bgr: np.ndarray, mask: np.ndarray, radius: float = 5.0, method: str = "telea") -> np.ndarray:
    """mask: uint8 0/255 cung kich thuoc frame (255 = vung can ve lai).
    Tra ve frame moi da inpaint toan bo (phan ngoai mask giu nguyen y het
    cv2.inpaint tra ve, ban than cv2.inpaint da chi sua doi vung mask)."""
    flag = _METHODS.get(method, cv2.INPAINT_TELEA)
    r = max(1.0, min(15.0, float(radius)))
    return cv2.inpaint(frame_bgr, mask, r, flag)
