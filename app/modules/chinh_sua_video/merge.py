"""Normalize and concatenate multiple videos into one MP4."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .errors import InvalidVideoRequest
from .ffmpeg_tools import run_tool
from .probe import VideoInfo, probe_video


def _even(value: int) -> int:
    return value if value % 2 == 0 else value - 1


def _normalize(info: VideoInfo, output: Path, width: int, height: int, fps: int) -> None:
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps},setsar=1"
    )
    args = ["-hide_banner", "-loglevel", "error", "-y", "-i", str(info.path)]
    if info.has_audio:
        args += ["-map", "0:v:0", "-map", "0:a:0", "-af", "aresample=async=1:first_pts=0,apad"]
    else:
        args += [
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0",
        ]
    args += [
        "-vf", video_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        "-t", f"{info.duration:.6f}", "-shortest", "-movflags", "+faststart", str(output),
    ]
    run_tool(args)


def merge_videos(sources: list[str | Path], output: str | Path) -> Path:
    if len(sources) < 2:
        raise InvalidVideoRequest("merge_videos requires at least two input videos")

    infos = [probe_video(source) for source in sources]
    width = max(2, _even(infos[0].width))
    height = max(2, _even(infos[0].height))
    fps = infos[0].fps
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="video_merge_", dir=str(destination.parent)) as tmp:
        temp_dir = Path(tmp)
        normalized: list[Path] = []
        for index, info in enumerate(infos):
            normalized_path = temp_dir / f"clip_{index:04d}.mp4"
            _normalize(info, normalized_path, width, height, fps)
            normalized.append(normalized_path)

        concat_file = temp_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in normalized),
            encoding="utf-8",
        )
        run_tool([
            "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", "-movflags", "+faststart", str(destination),
        ])
    return destination
