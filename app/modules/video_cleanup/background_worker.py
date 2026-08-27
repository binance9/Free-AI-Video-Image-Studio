"""Isolated rembg video worker. Emits JSON progress lines on stdout."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def emit(progress: int, stage: str, detail: str = "") -> None:
    print(json.dumps({"progress": int(progress), "stage": stage, "detail": detail}, ensure_ascii=False), flush=True)


def parse_color(value: str) -> tuple[int, int, int]:
    raw = (value or "#00ff00").strip().lstrip("#")
    if len(raw) != 6:
        raw = "00ff00"
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        r, g, b = 0, 255, 0
    return r, g, b


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--model", default="u2net_human_seg")
    parser.add_argument("--mode", choices=["transparent", "solid"], default="transparent")
    parser.add_argument("--color", default="#00ff00")
    args = parser.parse_args()

    os.environ.setdefault("OMP_NUM_THREADS", "4")
    import cv2
    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    from rembg import new_session, remove

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
    if width <= 0 or height <= 0:
        raise RuntimeError("Không đọc được kích thước video")

    providers = ort.get_available_providers()
    preferred = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in providers]
    emit(10, "Nạp AI xóa nền", f"Model {args.model} · {'CUDA' if 'CUDAExecutionProvider' in preferred else 'CPU'}")
    session = new_session(args.model, providers=preferred or None)
    emit(24, "AI xóa nền đã sẵn sàng", f"{width}×{height} · {fps:.2f} FPS · {total or '?'} frame")

    if args.mode == "transparent":
        pix_fmt = "bgra"
        encode = [
            args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "pipe:0",
            "-i", str(src), "-map", "0:v:0", "-map", "1:a?",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "28", "-b:v", "0", "-auto-alt-ref", "0",
            "-c:a", "libopus", "-shortest", str(out),
        ]
    else:
        pix_fmt = "bgr24"
        encode = [
            args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", pix_fmt, "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "pipe:0",
            "-i", str(src), "-map", "0:v:0", "-map", "1:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(out),
        ]
    ff = subprocess.Popen(encode, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if ff.stdin is None:
        raise RuntimeError("Không mở được FFmpeg pipe")

    r_bg, g_bg, b_bg = parse_color(args.color)
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgba_img = remove(Image.fromarray(rgb), session=session)
            rgba = np.asarray(rgba_img.convert("RGBA"), dtype=np.uint8)
            if args.mode == "transparent":
                encoded_frame = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
            else:
                alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
                fg = rgba[:, :, :3].astype(np.float32)
                bg = np.empty_like(fg)
                bg[:, :, 0], bg[:, :, 1], bg[:, :, 2] = r_bg, g_bg, b_bg
                mixed = (fg * alpha + bg * (1.0 - alpha)).clip(0, 255).astype(np.uint8)
                encoded_frame = cv2.cvtColor(mixed, cv2.COLOR_RGB2BGR)
            ff.stdin.write(encoded_frame.tobytes())
            index += 1
            if index == 1 or index % max(1, int(fps)) == 0:
                ratio = (index / total) if total > 0 else 0.0
                pct = 25 + int(min(1.0, ratio) * 65) if total > 0 else min(88, 25 + index // max(1, int(fps * 2)))
                emit(pct, "Đang xóa nền từng frame", f"{index} / {total or '?'} frame")
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
        raise RuntimeError("Không tạo được video sau khi xóa nền")
    emit(96, "Đã xóa nền", "Đang đưa kết quả vào editor")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit(0, "Lỗi xóa nền", str(exc))
        print(str(exc), file=sys.stderr, flush=True)
        raise
