"""Group word-level timestamps into readable subtitle segments."""
from __future__ import annotations


def group_words(words: list[dict], max_chars: int = 42, max_seconds: float = 4.5) -> list[dict]:
    out, current = [], []
    start = 0.0
    for word in words:
        text = str(word.get("word") or word.get("text") or "").strip()
        if not text:
            continue
        wstart, wend = float(word.get("start") or 0), float(word.get("end") or wstart)
        if not current:
            start = wstart
        candidate = " ".join(x[0] for x in current + [(text, wend)])
        long_enough = len(candidate) > max_chars or (wend - start) > max_seconds
        if current and long_enough:
            out.append({"start": start, "end": current[-1][1], "text": " ".join(x[0] for x in current)})
            current, start = [], wstart
        current.append((text, wend))
        if text.endswith((".", "!", "?", "…")) and len(current) >= 3:
            out.append({"start": start, "end": wend, "text": " ".join(x[0] for x in current)})
            current = []
    if current:
        out.append({"start": start, "end": current[-1][1], "text": " ".join(x[0] for x in current)})
    return out
