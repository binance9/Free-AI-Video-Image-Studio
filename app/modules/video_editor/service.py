"""Small service API the bot planner/executor can call."""

from __future__ import annotations

from pathlib import Path

from .cut import cut_video as _cut_video
from .merge import merge_videos as _merge_videos
from .render import render_layers as _render_layers


def cut_video(source: str | Path, output: str | Path, start: float, end: float) -> Path:
    return _cut_video(source, output, start, end)


def merge_videos(sources: list[str | Path], output: str | Path) -> Path:
    return _merge_videos(sources, output)


class VideoEditor:
    """Facade for deterministic edit operations."""

    def cut(self, source: str | Path, output: str | Path, start: float, end: float) -> Path:
        return cut_video(source, output, start, end)

    def merge(self, sources: list[str | Path], output: str | Path) -> Path:
        return merge_videos(sources, output)

    def render(self, source, output, layers, workspace, session_id) -> Path:
        return _render_layers(source, output, layers, workspace, session_id)
