"""Select a high-energy short excerpt using local RMS analysis."""
from __future__ import annotations

import math
import tempfile
import wave
from pathlib import Path

from app.modules.video_editor.ffmpeg_tools import run_tool


def choose_excerpt(source: str | Path, clip_seconds: float) -> float:
    clip_seconds = max(2.0, float(clip_seconds))
    with tempfile.TemporaryDirectory(prefix="music_rms_") as tmp:
        wav = Path(tmp) / "mono.wav"
        run_tool(["-hide_banner","-loglevel","error","-y","-i",str(source),"-vn","-ac","1","-ar","8000","-c:a","pcm_s16le",str(wav)])
        with wave.open(str(wav), "rb") as fh:
            rate = fh.getframerate()
            frames = fh.readframes(fh.getnframes())
    if not frames:
        return 0.0
    import array
    samples = array.array("h")
    samples.frombytes(frames)
    bucket = max(1, rate // 2)
    energies = []
    for i in range(0, len(samples), bucket):
        chunk = samples[i:i+bucket]
        if not chunk:
            break
        energies.append(math.sqrt(sum(v*v for v in chunk) / len(chunk)))
    window = max(1, int(round(clip_seconds * 2)))
    if len(energies) <= window:
        return 0.0
    best_i, best_score = 0, -1.0
    for i in range(0, len(energies) - window + 1):
        score = sum(energies[i:i+window]) / window
        # Prefer not to start on the first half-second when choices are similar.
        if i == 0:
            score *= 0.97
        if score > best_score:
            best_i, best_score = i, score
    return best_i * 0.5
