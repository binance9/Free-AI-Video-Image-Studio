from __future__ import annotations
import json
import time
from pathlib import Path

try:
    import numpy as np
except Exception:
    np = None


class OwnerVoiceVerifier:
    """
    Voiceprint local nhẹ, chỉ dùng NumPy (AI Video Factory vốn đã dùng NumPy).
    Mục tiêu: bỏ qua giọng người khác trong sử dụng thông thường.
    Không phải sinh trắc học pháp y; không chống replay/voice-clone tinh vi.
    """

    def __init__(self, profile_path: str | Path, threshold: float = 0.84):
        self.path = Path(profile_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = float(threshold)
        self.samples = []
        self.profile = None
        self.load()

    @property
    def available(self):
        return np is not None

    @property
    def enrolled(self):
        return bool(self.profile and self.profile.get("centroid"))

    def load(self):
        if self.path.is_file():
            try:
                self.profile = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.profile = None

    @staticmethod
    def _pcm(raw: bytes):
        if np is None:
            raise RuntimeError("Thiếu numpy")
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32)
        if x.size == 0:
            raise ValueError("Không có âm thanh")
        return x / 32768.0

    @staticmethod
    def _trim(x):
        peak = float(np.max(np.abs(x))) if x.size else 0.0
        if peak < 0.012:
            raise ValueError("Giọng quá nhỏ")
        x = x / max(peak, 1e-6)
        ids = np.flatnonzero(np.abs(x) > 0.02)
        if ids.size:
            a = max(0, int(ids[0]) - 1200)
            b = min(len(x), int(ids[-1]) + 1200)
            x = x[a:b]
        return x

    @classmethod
    def embedding(cls, raw: bytes, sample_rate: int = 16000):
        x = cls._trim(cls._pcm(raw))
        if len(x) < int(sample_rate * 0.7):
            raise ValueError("Đoạn giọng quá ngắn")

        frame = 512
        hop = 256
        if len(x) < frame:
            raise ValueError("Mẫu giọng quá ngắn")

        window = np.hanning(frame).astype(np.float32)
        feats = []
        for start in range(0, len(x) - frame + 1, hop):
            f = x[start:start+frame] * window
            energy = float(np.mean(f*f) + 1e-8)
            zcr = float(np.mean(np.abs(np.diff(np.signbit(f))).astype(np.float32)))

            spec = np.abs(np.fft.rfft(f)) + 1e-8
            power = spec * spec
            freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)

            total = float(power.sum()) + 1e-8
            centroid = float((freqs * power).sum() / total) / (sample_rate / 2)
            spread = float(np.sqrt((((freqs/(sample_rate/2) - centroid)**2) * power).sum() / total))

            # Coarse spectral bands make a compact speaker timbre signature.
            bands = []
            edges = np.linspace(0, len(power), 17, dtype=int)
            for i in range(16):
                a, b = edges[i], max(edges[i]+1, edges[i+1])
                bands.append(float(np.log(power[a:b].mean() + 1e-8)))

            feats.append([np.log(energy), zcr, centroid, spread, *bands])

        F = np.asarray(feats, dtype=np.float32)
        if len(F) < 8:
            raise ValueError("Không đủ khung giọng")

        # Normalize per recording, then summarize temporal distribution.
        mu = F.mean(axis=0)
        sd = F.std(axis=0) + 1e-5
        N = (F - mu) / sd

        vec = np.concatenate([
            mu,
            F.std(axis=0),
            np.percentile(F, 25, axis=0),
            np.percentile(F, 50, axis=0),
            np.percentile(F, 75, axis=0),
            N.mean(axis=0),
            N.std(axis=0),
        ]).astype(np.float32)

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    @staticmethod
    def cosine(a, b):
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        den = float(np.linalg.norm(a) * np.linalg.norm(b))
        return 0.0 if den <= 1e-8 else float(np.dot(a, b) / den)

    def reset_enrollment(self):
        self.samples = []

    def add_enrollment_sample(self, raw: bytes, sample_rate: int = 16000, target: int = 5):
        self.samples.append(self.embedding(raw, sample_rate))
        count = len(self.samples)
        if count < target:
            return {"done": False, "count": count, "target": target}

        arr = np.vstack(self.samples[-target:])
        centroid = arr.mean(axis=0)
        centroid /= (np.linalg.norm(centroid) or 1.0)
        scores = [self.cosine(e, centroid) for e in arr]

        # Calibrate to the owner's own enrollment samples.
        threshold = max(0.76, min(float(np.percentile(scores, 10)) - 0.025, 0.94))
        self.profile = {
            "version": 2,
            "created_at": time.time(),
            "centroid": centroid.astype(float).tolist(),
            "threshold": threshold,
            "enrollment_scores": [float(x) for x in scores],
        }
        self.path.write_text(
            json.dumps(self.profile, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        self.samples = []
        return {"done": True, "count": target, "target": target, "threshold": threshold}

    def verify(self, raw: bytes, sample_rate: int = 16000):
        if not self.enrolled:
            return False, 0.0
        emb = self.embedding(raw, sample_rate)
        score = self.cosine(emb, self.profile["centroid"])
        threshold = float(self.profile.get("threshold", self.threshold))
        return score >= threshold, score
