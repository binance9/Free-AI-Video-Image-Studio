"""Hau xu ly sau inpaint: on dinh theo thoi gian (giam nhap nhay), tron mep
giua vung inpaint va anh goc, va sharpen nhe vung vua phuc hoi.

Khong co buoc nao o day dung blur de "che" noi dung - GaussianBlur ben trong
sharpen_region() chi la phep tinh trung gian chuan cua ky thuat unsharp mask
(anh sac net = anh goc + (anh goc - anh mo) * amount), ket qua cuoi cung la
anh SAC NET hon, khong phai anh mo.
"""
from __future__ import annotations

import cv2
import numpy as np


class TemporalStabilizer:
    """Giam nhap nhay (flicker) giua cac frame da inpaint bang EMA (exponential
    moving average), nhung EMA duoc lay trong khung toa do CUC BO cua bbox
    dang track (roi resize ve kich thuoc bbox hien tai neu bbox doi kich
    thuoc) - nho vay khi camera pan/zoom, "mieng va" duoc EMA van di theo
    dung vi tri/kich thuoc moi, khong bi lem hay dinh vao vi tri cu."""

    def __init__(self, ema_alpha: float = 0.55):
        self.ema_alpha = float(np.clip(ema_alpha, 0.0, 1.0))
        self._prev_patch: np.ndarray | None = None
        self._prev_size: tuple[int, int] | None = None

    def stabilize(self, inpainted_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return inpainted_bgr
        patch = inpainted_bgr[y:y + h, x:x + w].astype(np.float32)

        if self._prev_patch is None:
            blended = patch
        else:
            prev = self._prev_patch
            if self._prev_size != (w, h):
                prev = cv2.resize(prev, (w, h), interpolation=cv2.INTER_LINEAR)
            blended = self.ema_alpha * patch + (1.0 - self.ema_alpha) * prev

        self._prev_patch = blended
        self._prev_size = (w, h)

        out = inpainted_bgr.copy()
        out[y:y + h, x:x + w] = np.clip(blended, 0, 255).astype(np.uint8)
        return out


def blend_edges(original_bgr: np.ndarray, inpainted_bgr: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Tron mep giua anh goc va anh da inpaint bang alpha feather (xem
    video_mask.feather_mask): alpha=1 giu nguyen ket qua inpaint, alpha=0
    giu nguyen anh goc, vung chuyen tiep noi suy tuyen tinh - day la buoc
    chong "duong vien cung/rang cua", khong lam mo noi dung ben trong mask."""
    a = alpha[..., None].astype(np.float32)
    out = inpainted_bgr.astype(np.float32) * a + original_bgr.astype(np.float32) * (1.0 - a)
    return np.clip(out, 0, 255).astype(np.uint8)


def sharpen_region(frame_bgr: np.ndarray, mask: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """Unsharp mask NHE, CHI ap dung trong vung mask (vung vua phuc hoi) de
    lay lai do net (inpaint/EMA co xu huong lam anh hoi mem) - phan con lai
    cua frame giu nguyen, khong dong toi."""
    amount = float(np.clip(amount, 0.0, 1.5))
    if amount <= 0:
        return frame_bgr
    blurred = cv2.GaussianBlur(frame_bgr, (0, 0), sigmaX=1.2)
    sharpened = cv2.addWeighted(frame_bgr, 1.0 + amount, blurred, -amount, 0)
    m = mask > 0
    out = frame_bgr.copy()
    out[m] = sharpened[m]
    return out
