"""Free local speech-to-text using faster-whisper."""
from __future__ import annotations

from pathlib import Path
from threading import Lock


class LocalCaptionService:
    def __init__(self, model_name: str = "small", model_dir: str | Path | None = None):
        self.model_name = model_name
        self.model_dir = str(Path(model_dir).resolve()) if model_dir else None
        self._model = None
        self._lock = Lock()

    def transcribe(self, audio_path: str | Path) -> dict:
        model = self._get_model()
        segments_iter, info = model.transcribe(
            str(audio_path), beam_size=5, vad_filter=True, word_timestamps=True
        )
        segments = []
        full_text = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if not text:
                continue
            segments.append({"start": round(float(seg.start), 3), "end": round(float(seg.end), 3), "text": text})
            full_text.append(text)
            if len(segments) >= 150:
                break
        return {
            "text": " ".join(full_text),
            "segments": segments,
            "language": getattr(info, "language", "") or "",
            "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
            "engine": f"faster-whisper:{self.model_name}",
        }

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ValueError("Chưa cài Whisper local. Chạy SETUP_FREE_AI.bat một lần.") from exc
            self._model = WhisperModel(
                self.model_name,
                device="auto",
                compute_type="default",
                download_root=self.model_dir,
            )
            return self._model
