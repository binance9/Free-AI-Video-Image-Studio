"""Worker xoa chu/logo/icon that su bang pipeline:

    mask (video_mask) -> track mask qua frame (video_tracking) ->
    inpaint tung frame (video_inpaint) -> on dinh theo thoi gian +
    tron mep + sharpen nhe (temporal_blend)

KHONG dung blur/mosaic de "che" vung xoa - vung mask duoc VE LAI bang
cv2.inpaint (cau truc that, tu vien anh xung quanh), sau do moi on dinh
theo thoi gian de giam nhap nhay va tron mep de khong bi duong vien cung.

Giu nguyen hop dong CLI cu (--input --output --ffmpeg --x --y --w --h
--radius) de job_manager.py khong can doi cach goi subprocess; --feather la
tham so moi, co gia tri mac dinh an toan neu khong duoc truyen.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tren Windows, stdout/stderr cua tien trinh con mac dinh dung codepage ANSI
# (vd cp1252) khong ma hoa duoc tieng Viet co dau - ep utf-8 de emit() JSON
# (co chua tieng Viet) khong bao gio bi UnicodeEncodeError khi job_manager
# doc qua pipe.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


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
    parser.add_argument("--feather", type=int, default=6)
    args = parser.parse_args()

    import cv2

    from video_inpaint import inpaint_frame
    from video_mask import build_rect_mask, feather_mask, dilate_mask
    from video_tracking import MaskTracker
    from temporal_blend import TemporalStabilizer, blend_edges, sharpen_region

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
    x = max(0, min(width - 2, args.x))
    y = max(0, min(height - 2, args.y))
    w = max(2, min(width - x, args.w))
    h = max(2, min(height - y, args.h))

    tracker = MaskTracker((x, y, w, h), (height, width))
    stabilizer = TemporalStabilizer(ema_alpha=0.55)

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
    emit(12, "Chuẩn bị vùng xóa", f"x={x}, y={y}, {w}×{h} · track+inpaint")
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            bx, by, bw, bh = tracker.update(frame)
            mask = build_rect_mask((height, width), (bx, by, bw, bh), padding=0)
            alpha = feather_mask(mask, feather_px=args.feather)

            inpainted = inpaint_frame(frame, mask, radius=args.radius, method="telea")
            inpainted = stabilizer.stabilize(inpainted, (bx, by, bw, bh))
            blended = blend_edges(frame, inpainted, alpha)
            sharp_mask = dilate_mask(mask, pixels=2)
            cleaned = sharpen_region(blended, sharp_mask, amount=0.5)

            ff.stdin.write(cleaned.tobytes())
            index += 1
            if index == 1 or index % max(1, int(fps)) == 0:
                ratio = (index / total) if total > 0 else 0.0
                pct = 15 + int(min(1.0, ratio) * 75) if total > 0 else min(88, 15 + index // max(1, int(fps * 2)))
                emit(pct, "Đang xóa chữ / icon", f"{index} / {total or '?'} frame · track+inpaint")
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
