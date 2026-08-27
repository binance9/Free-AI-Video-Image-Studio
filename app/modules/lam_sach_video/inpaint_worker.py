"""Frame-by-frame OpenCV inpaint for fixed text/logo/icon rectangles."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def emit(progress: int, stage: str, detail: str = "") -> None:
    print(json.dumps({"progress": int(progress), "stage": stage, "detail": detail}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--x", type=int, required=True)
    parser.add_argument("--y", type=int, required=True)
    parser.add_argument("--w", type=int, required=True)
    parser.add_argument("--h", type=int, required=True)
    parser.add_argument("--radius", type=float, default=5.0)
    args = parser.parse_args()

    import cv2
    import numpy as np

    src = Path(args.input).resolve()
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError("Không mở được video nguồn")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    x = max(0, min(width - 2, args.x)); y = max(0, min(height - 2, args.y))
    w = max(2, min(width - x, args.w)); h = max(2, min(height - y, args.h))
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y:y+h, x:x+w] = 255

    cmd = [
        args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "pipe:0",
        "-i", str(src), "-map", "0:v:0", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(out),
    ]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if ff.stdin is None:
        raise RuntimeError("Không mở được FFmpeg pipe")
    emit(12, "Chuẩn bị vùng xóa", f"x={x}, y={y}, {w}×{h}")
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            cleaned = cv2.inpaint(frame, mask, max(1.0, args.radius), cv2.INPAINT_TELEA)
            ff.stdin.write(cleaned.tobytes())
            index += 1
            if index == 1 or index % max(1, int(fps)) == 0:
                ratio = (index / total) if total > 0 else 0.0
                pct = 15 + int(min(1.0, ratio) * 75) if total > 0 else min(88, 15 + index // max(1, int(fps * 2)))
                emit(pct, "Đang xóa chữ / icon", f"{index} / {total or '?'} frame · inpaint")
    finally:
        cap.release()
        try:
            ff.stdin.close()
        except Exception:
            pass
    stderr = (ff.stderr.read().decode("utf-8", errors="replace") if ff.stderr else "")
    rc = ff.wait()
    if rc != 0:
        raise RuntimeError("FFmpeg xuất video lỗi: " + stderr[-1000:])
    if not out.is_file() or out.stat().st_size < 1024:
        raise RuntimeError("Không tạo được video sau khi xóa vùng")
    emit(96, "Đã xóa vùng", "Đang đưa kết quả vào editor")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit(0, "Lỗi xóa vùng", str(exc))
        print(str(exc), file=sys.stderr, flush=True)
        raise
