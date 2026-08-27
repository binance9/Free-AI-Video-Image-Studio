"""Frame-accurate video cutting with H.264/AAC output."""

from __future__ import annotations

from pathlib import Path

from .errors import InvalidVideoRequest
from .ffmpeg_tools import run_tool
from .probe import probe_video


def cut_video(
    source: str | Path,
    output: str | Path,
    start_seconds: float,
    end_seconds: float,
) -> Path:
    info = probe_video(source)
    start = float(start_seconds)
    end = float(end_seconds)
    if start < 0:
        raise InvalidVideoRequest("start_seconds must be >= 0")
    if end <= start:
        raise InvalidVideoRequest("end_seconds must be greater than start_seconds")
    if start >= info.duration:
        raise InvalidVideoRequest("start_seconds is outside the video duration")

    end = min(end, info.duration)
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start

    run_tool([
        "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(info.path),
        "-ss", f"{start:.6f}",
        "-t", f"{duration:.6f}",
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(destination),
    ])
    return destination
