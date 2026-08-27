"""Render image, sticker, GIPHY and text layers over the current video."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .errors import InvalidVideoRequest
from .ffmpeg_tools import run_tool
from .probe import probe_video
from .text_image import render_text_png


def _local_source(layer: dict, workspace, session_id: str) -> Path:
    kind = layer.get("source_kind")
    if kind == "asset":
        return workspace.asset_path(session_id, str(layer.get("source", "")))
    if kind == "builtin":
        return workspace.builtin_sticker_path(str(layer.get("source", "")))
    raise InvalidVideoRequest("Unknown local overlay source")


def _giphy_url(value: str) -> str:
    parsed = urlparse(value or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "giphy.com" or host.endswith(".giphy.com")):
        raise InvalidVideoRequest("Invalid GIPHY media URL")
    return value


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def render_layers(source: str | Path, output: str | Path, layers: list[dict], workspace, session_id: str) -> Path:
    info = probe_video(source)
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not layers:
        # Re-encode only when requested by export; keeps output predictable.
        run_tool([
            "-hide_banner", "-loglevel", "error", "-y", "-i", str(info.path),
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(destination),
        ])
        return destination

    with tempfile.TemporaryDirectory(prefix="overlay_", dir=str(destination.parent)) as tmp:
        temp = Path(tmp)
        args = ["-hide_banner", "-loglevel", "error", "-y", "-i", str(info.path)]
        prepared: list[dict] = []
        for index, raw in enumerate(layers):
            layer = dict(raw)
            kind = layer.get("type")
            if kind == "text":
                font_ratio = _clamp(layer.get("font_size_ratio", 0.05), 0.012, 0.30)
                font_size = max(10, int(info.width * font_ratio))
                text_path = temp / f"text_{index:03d}.png"
                render_text_png(
                    str(layer.get("text", "Text")), text_path, font_size,
                    str(layer.get("color", "#ffffff")), str(layer.get("outline_color", "#000000")),
                    int(layer.get("outline_width", 3)), str(layer.get("background", "#000000")),
                    _clamp(layer.get("background_opacity", 0), 0, 1),
                    font_family=str(layer.get("font_family", "segoe")),
                    shadow_color=str(layer.get("shadow_color", "#000000")),
                    shadow_opacity=_clamp(layer.get("shadow_opacity", 0), 0, 1),
                    shadow_blur=int(layer.get("shadow_blur", 0)),
                )
                source_value = str(text_path)
                args += ["-loop", "1", "-framerate", str(info.fps), "-i", source_value]
                layer["source_kind"] = "temp"
            elif layer.get("source_kind") == "giphy":
                source_value = _giphy_url(str(layer.get("source", "")))
                args += ["-stream_loop", "-1", "-i", source_value]
            else:
                path = _local_source(layer, workspace, session_id)
                source_value = str(path)
                if path.suffix.lower() == ".gif":
                    args += ["-stream_loop", "-1", "-i", source_value]
                else:
                    args += ["-loop", "1", "-framerate", str(info.fps), "-i", source_value]
            prepared.append(layer)

        filters: list[str] = []
        current = "[0:v]"
        for index, layer in enumerate(prepared, start=1):
            width_ratio = _clamp(layer.get("width_ratio", 0.22), 0.02, 1.5)
            width_px = max(8, int(info.width * width_ratio))
            opacity = _clamp(layer.get("opacity", 1), 0.05, 1)
            rotation = _clamp(layer.get("rotation", 0), -360, 360)
            start = _clamp(layer.get("start", 0), 0, info.duration)
            end = _clamp(layer.get("end", info.duration), start, info.duration)
            x = _clamp(layer.get("x", 0.5), -0.5, 1.5)
            y = _clamp(layer.get("y", 0.5), -0.5, 1.5)
            pre = f"ov{index}"
            rotate = ""
            if abs(rotation) > 0.01:
                radians = rotation * math.pi / 180.0
                rotate = f",rotate={radians:.8f}:ow=rotw(iw):oh=roth(ih):c=none"
            filters.append(
                f"[{index}:v]setpts=PTS-STARTPTS,scale={width_px}:-1,format=rgba"
                f"{rotate},colorchannelmixer=aa={opacity:.4f}[{pre}]"
            )
            out = f"v{index}"
            xexpr = f"main_w*{x:.6f}-overlay_w/2"
            yexpr = f"main_h*{y:.6f}-overlay_h/2"
            filters.append(
                f"{current}[{pre}]overlay=x='{xexpr}':y='{yexpr}':"
                f"enable='between(t,{start:.6f},{end:.6f})':eof_action=pass:repeatlast=0[{out}]"
            )
            current = f"[{out}]"

        args += [
            "-filter_complex", ";".join(filters), "-map", current, "-map", "0:a?",
            "-t", f"{info.duration:.6f}", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(destination),
        ]
        run_tool(args)
    return destination
