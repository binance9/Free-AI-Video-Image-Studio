"""Mix a selected music excerpt into a video as a new non-destructive version."""
from __future__ import annotations

from pathlib import Path

from app.modules.video_editor.ffmpeg_tools import run_tool
from app.modules.video_editor.probe import probe_video
from .clip_selector import choose_excerpt


def mix_music(video: str | Path, music: str | Path, output: str | Path, *, clip_duration: float = 15, insert_at: float = 0, volume: float = 0.35, keep_original: bool = True, smart_excerpt: bool = True) -> dict:
    info = probe_video(video)
    clip_duration = max(2.0, min(float(clip_duration), info.duration))
    insert_at = max(0.0, min(float(insert_at), max(0.0, info.duration - 0.25)))
    usable = min(clip_duration, info.duration - insert_at)
    volume = max(0.0, min(1.5, float(volume)))
    source_start = choose_excerpt(music, usable) if smart_excerpt else 0.0
    delay_ms = int(round(insert_at * 1000))
    fade_out_start = max(0.0, usable - min(1.0, usable / 3))
    destination = Path(output).resolve()
    music_filter = (
        f"[1:a]atrim=start={source_start:.3f}:duration={usable:.3f},asetpts=PTS-STARTPTS,"
        f"volume={volume:.4f},afade=t=in:st=0:d={min(.5,usable/4):.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={min(1.0,usable/3):.3f},"
        f"adelay={delay_ms}:all=1,apad,atrim=duration={info.duration:.3f}[music]"
    )
    args = ["-hide_banner","-loglevel","error","-y","-i",str(info.path),"-i",str(music)]
    if keep_original and info.has_audio:
        filters = music_filter + f";[0:a]apad,atrim=duration={info.duration:.3f}[orig];[orig][music]amix=inputs=2:duration=first:dropout_transition=1[a]"
        args += ["-filter_complex",filters,"-map","0:v:0","-map","[a]"]
    else:
        args += ["-filter_complex",music_filter,"-map","0:v:0","-map","[music]"]
    args += ["-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",str(destination)]
    run_tool(args)
    return {"output": destination, "source_start": round(source_start, 3), "clip_duration": round(usable, 3)}
