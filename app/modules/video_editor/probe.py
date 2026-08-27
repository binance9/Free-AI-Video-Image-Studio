"""Read video metadata required by cut and merge operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidVideoRequest, VideoEditorError
from .ffmpeg_tools import run_tool


@dataclass(frozen=True, slots=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: int
    duration: float
    has_audio: bool


def _fps(value: str | None) -> int:
    try:
        if not value:
            return 30
        numerator, denominator = value.split("/", 1)
        raw = float(numerator) / max(float(denominator), 1.0)
        return max(1, min(60, int(round(raw))))
    except (ValueError, ZeroDivisionError):
        return 30


def probe_video(path: str | Path) -> VideoInfo:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise InvalidVideoRequest(f"Input video does not exist: {source}")

    result = run_tool(
        [
            "-v", "error",
            "-show_entries", "stream=codec_type,width,height,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json",
            str(source),
        ],
        tool="ffprobe",
    )
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video = next(item for item in streams if item.get("codec_type") == "video")
        duration = float(payload.get("format", {}).get("duration", 0.0))
        width = int(video.get("width", 0))
        height = int(video.get("height", 0))
    except (StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoEditorError(f"Cannot read video metadata: {source}") from exc

    if width <= 0 or height <= 0 or duration <= 0:
        raise VideoEditorError(f"Invalid video metadata: {source}")

    return VideoInfo(
        path=source,
        width=width,
        height=height,
        fps=_fps(video.get("r_frame_rate")),
        duration=duration,
        has_audio=any(item.get("codec_type") == "audio" for item in streams),
    )
