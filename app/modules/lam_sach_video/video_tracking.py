"""Theo doi (track) vung can xoa qua cac frame bang optical flow.

Khong dung tracker CSRT/KCF (can opencv-contrib, khong co san trong venv du
an - xem MODULE_STATUS.md) - dung goodFeaturesToTrack + calcOpticalFlowPyrLK
(Lucas-Kanade), uoc luong dich chuyen (translation, tu median cua vector
flow) va ty le phong to/thu nho (scale, tu do phong diem quanh tam) de bam
theo pan/zoom camera co ban. Scale duoc gioi han moi frame de mask "khong
duoc lan qua rong" ngay ca khi tracking sai lech.
"""
from __future__ import annotations

import cv2
import numpy as np

LK_PARAMS = dict(
    winSize=(21, 21),
    maxLevel=3,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
)
FEATURE_PARAMS = dict(maxCorners=60, qualityLevel=0.01, minDistance=6, blockSize=7)
MIN_TRACK_POINTS = 6
# Gioi han scale moi frame de tranh mask phinh to dan qua nhieu frame lien
# tiep (bam sai) - dung voi yeu cau "mask khong duoc lan qua rong".
SCALE_MIN = 0.85
SCALE_MAX = 1.18
# Camera dung yen van co the sinh flow "gia" vai phan muoi pixel (nhieu/rung
# keypoint) - bo qua dich chuyen qua nho de khong bi "troi" (drift) dan qua
# nhieu frame tren canh (da phat hien qua test that: khong co deadzone lam
# mask lech dan, de lo 1 goc vung logo goc chua duoc xoa).
DRIFT_DEADZONE_PX = 0.75
# Gioi han dich chuyen moi frame: 1 uoc luong flow sai (do noi dung dong
# gia tao trong canh - vd testsrc) khong the lam bbox nhay xa trong 1 frame;
# pan/zoom that van duoc theo du tot vi dich chuyen cong don qua nhieu frame.
MAX_STEP_PX = 6.0


class MaskTracker:
    """Bam theo 1 vung chu nhat (bbox pixel) qua cac frame video lien tiep."""

    def __init__(self, bbox: tuple[int, int, int, int], frame_shape: tuple[int, int]):
        self.bbox = bbox
        self.frame_h, self.frame_w = frame_shape
        self._prev_gray: np.ndarray | None = None
        self._pts: np.ndarray | None = None

    def _seed_points(self, gray: np.ndarray) -> np.ndarray | None:
        x, y, w, h = self.bbox
        margin = max(w, h)
        x0 = max(0, x - margin)
        y0 = max(0, y - margin)
        x1 = min(self.frame_w, x + w + margin)
        y1 = min(self.frame_h, y + h + margin)
        if x1 <= x0 or y1 <= y0:
            return None
        roi = gray[y0:y1, x0:x1]
        pts = cv2.goodFeaturesToTrack(roi, **FEATURE_PARAMS)
        if pts is None:
            return None
        pts[:, 0, 0] += x0
        pts[:, 0, 1] += y0
        return pts

    def update(self, frame_bgr: np.ndarray) -> tuple[int, int, int, int]:
        """Tra ve bbox moi (x, y, w, h) da bam theo chuyen dong khung hinh nay."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is None:
            self._pts = self._seed_points(gray)
            self._prev_gray = gray
            return self.bbox

        if self._pts is None or len(self._pts) < MIN_TRACK_POINTS:
            self._pts = self._seed_points(gray)
            self._prev_gray = gray
            return self.bbox

        new_pts, status, _err = cv2.calcOpticalFlowPyrLK(self._prev_gray, gray, self._pts, None, **LK_PARAMS)
        if new_pts is None:
            self._prev_gray = gray
            return self.bbox

        status = status.reshape(-1).astype(bool)
        old_ok = self._pts[status]
        new_ok = new_pts[status]

        if len(new_ok) >= MIN_TRACK_POINTS:
            old_xy = old_ok.reshape(-1, 2)
            new_xy = new_ok.reshape(-1, 2)
            flow = new_xy - old_xy
            dx, dy = float(np.median(flow[:, 0])), float(np.median(flow[:, 1]))
            if abs(dx) < DRIFT_DEADZONE_PX:
                dx = 0.0
            if abs(dy) < DRIFT_DEADZONE_PX:
                dy = 0.0
            dx = float(np.clip(dx, -MAX_STEP_PX, MAX_STEP_PX))
            dy = float(np.clip(dy, -MAX_STEP_PX, MAX_STEP_PX))

            old_center = old_xy.mean(axis=0)
            new_center = new_xy.mean(axis=0)
            old_spread = float(np.mean(np.linalg.norm(old_xy - old_center, axis=1))) + 1e-6
            new_spread = float(np.mean(np.linalg.norm(new_xy - new_center, axis=1))) + 1e-6
            scale = float(np.clip(new_spread / old_spread, SCALE_MIN, SCALE_MAX))

            x, y, w, h = self.bbox
            cx, cy = x + w / 2.0 + dx, y + h / 2.0 + dy
            new_w, new_h = w * scale, h * scale
            nx = int(round(cx - new_w / 2.0))
            ny = int(round(cy - new_h / 2.0))
            nx = max(0, min(self.frame_w - 4, nx))
            ny = max(0, min(self.frame_h - 4, ny))
            new_w = max(4, min(self.frame_w - nx, int(round(new_w))))
            new_h = max(4, min(self.frame_h - ny, int(round(new_h))))
            self.bbox = (nx, ny, new_w, new_h)
            self._pts = new_ok.reshape(-1, 1, 2)
        else:
            self._pts = self._seed_points(gray)

        self._prev_gray = gray
        return self.bbox
