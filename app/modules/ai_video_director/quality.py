from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def parse_duration(value: Any) -> float:
    """Safely parse a duration value that may be:
    - A float/int like 12.5
    - A MM:SS string like "0:00", "00:05", "01:23"
    - A HH:MM:SS string like "1:02:03"
    - None / empty / "N/A" → 0.0
    Never raises; always returns a float.
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s.upper() in ("N/A", "NA", "NULL", "NONE"):
        return 0.0
    # Already a plain float string like "12.5"
    if ":" not in s:
        try:
            return float(s)
        except ValueError:
            return 0.0
    # MM:SS or HH:MM:SS
    parts = s.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return 0.0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    # Fallback: try direct float
    try:
        return float(s)
    except ValueError:
        return 0.0


@dataclass
class QAResult:
    passed: bool
    score: float
    checks: dict[str, Any]
    issues: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def image_quality(path: str | Path) -> QAResult:
    """Cheap technical gate only; it never pretends to judge beauty/identity."""
    from PIL import Image, ImageFilter, ImageStat

    p = Path(path)
    issues: list[str] = []
    checks: dict[str, Any] = {"path": str(p)}
    if not p.is_file() or p.stat().st_size < 10_000:
        return QAResult(False, 0.0, checks, ["IMAGE_FILE_INVALID_OR_TOO_SMALL"])
    try:
        with Image.open(p) as im:
            im.load()
            w, h = im.size
            rgb = im.convert("RGB")
            gray = rgb.convert("L")
            stat = ImageStat.Stat(gray)
            mean = float(stat.mean[0])
            contrast = float(stat.stddev[0])
            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edge)
            sharpness = float(edge_stat.stddev[0])
            checks.update(width=w, height=h, mean_luma=round(mean, 2), contrast=round(contrast, 2), edge_detail=round(sharpness, 2), bytes=p.stat().st_size)
            if min(w, h) < 512:
                issues.append("IMAGE_RESOLUTION_LOW")
            if contrast < 10:
                issues.append("IMAGE_TOO_FLAT")
            if sharpness < 5:
                issues.append("IMAGE_TOO_BLURRY")
            if mean < 3:
                issues.append("IMAGE_NEAR_BLACK")
            if mean > 252:
                issues.append("IMAGE_NEAR_WHITE")
    except Exception as exc:
        return QAResult(False, 0.0, checks, [f"IMAGE_DECODE_FAILED:{exc}"])
    score = 10.0
    score -= 2.5 * len(issues)
    return QAResult(not issues, max(0.0, score), checks, issues)


def _ffprobe_json(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("Không tìm thấy ffprobe trong PATH")
    cp = subprocess.run(
        [ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.decode("utf-8", "replace")[-1200:])
    return json.loads(cp.stdout.decode("utf-8", "replace"))


def _ratio(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        a, b = value.split("/", 1)
        return float(a) / float(b)
    except Exception:
        try:
            return float(value)
        except Exception:
            return 0.0


def video_quality(path: str | Path, *, min_width: int = 640, min_height: int = 360, expected_duration: float | None = None) -> QAResult:
    """Technical video QA: readable stream, resolution, fps, duration and mostly-black output."""
    p = Path(path)
    issues: list[str] = []
    checks: dict[str, Any] = {"path": str(p)}
    if not p.is_file() or p.stat().st_size < 20_000:
        return QAResult(False, 0.0, checks, ["VIDEO_FILE_INVALID_OR_TOO_SMALL"])
    try:
        meta = _ffprobe_json(p)
    except Exception as exc:
        return QAResult(False, 0.0, checks, [f"FFPROBE_FAILED:{exc}"])
    streams = meta.get("streams") or []
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not vs:
        return QAResult(False, 0.0, checks, ["NO_VIDEO_STREAM"])
    width = int(vs.get("width") or 0)
    height = int(vs.get("height") or 0)
    avg_fps = _ratio(vs.get("avg_frame_rate"))
    r_fps = _ratio(vs.get("r_frame_rate"))
    duration = parse_duration(vs.get("duration") or (meta.get("format") or {}).get("duration") or 0.0)
    frame_count = 0
    for key in ("nb_read_frames", "nb_frames"):
        try:
            frame_count = int(vs.get(key) or 0)
        except Exception:
            frame_count = 0
        if frame_count > 0:
            break
    counted_fps = (float(frame_count) / duration) if frame_count > 0 and duration > 0 else 0.0
    candidates = [v for v in (avg_fps, r_fps, counted_fps) if 0.1 <= v <= 240.0]
    fps = max(candidates) if candidates else 0.0
    checks.update(
        width=width, height=height, fps=round(fps, 3),
        avg_fps=round(avg_fps, 3), r_fps=round(r_fps, 3), counted_fps=round(counted_fps, 3),
        frame_count=frame_count, duration=round(duration, 3), codec=vs.get("codec_name"), bytes=p.stat().st_size
    )
    if width < min_width or height < min_height:
        issues.append("VIDEO_RESOLUTION_LOW")
    if fps < 12:
        issues.append("VIDEO_FPS_TOO_LOW")
    if duration <= 0.25:
        issues.append("VIDEO_DURATION_INVALID")
    if expected_duration and abs(duration - expected_duration) > max(1.5, expected_duration * 0.45):
        issues.append("VIDEO_DURATION_MISMATCH")

    ff = shutil.which("ffmpeg")
    if ff and duration > 0:
        try:
            cp = subprocess.run(
                [ff, "-hide_banner", "-nostats", "-i", str(p), "-vf", "blackdetect=d=0.35:pix_th=0.03", "-an", "-f", "null", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(30, int(math.ceil(duration * 4))),
            )
            text = cp.stderr.decode("utf-8", "replace")
            black_total = 0.0
            for line in text.splitlines():
                if "black_duration:" in line:
                    try:
                        black_total += float(line.split("black_duration:", 1)[1].split()[0])
                    except Exception:
                        pass
            checks["black_seconds"] = round(black_total, 3)
            checks["black_ratio"] = round(black_total / duration, 3) if duration else 0.0
            if duration and black_total / duration > 0.60:
                issues.append("VIDEO_MOSTLY_BLACK")
        except Exception as exc:
            checks["blackdetect_warning"] = str(exc)
    score = 10.0
    score -= 2.0 * len(issues)
    return QAResult(not issues, max(0.0, score), checks, issues)
