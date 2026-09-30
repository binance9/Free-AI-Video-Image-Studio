from pathlib import Path
import tempfile

from PIL import Image

from app.modules.tao_video_ai.service import LocalVideoAIService, VideoAIWorkspace, _round_cogvideox_frames, _video_profile


def test_cogvideox_frame_rule():
    n = _round_cogvideox_frames(3, 16)
    assert n >= 17 and (n - 1) % 8 == 0


def test_profiles_are_16gb_sane():
    t = _video_profile("text_to_video", "balanced", 3, 16)
    assert t.width <= 720 and t.height <= 480 and t.duration == 3
    i = _video_profile("image_to_video", "balanced", 3, 16)
    assert i.width <= 1024 and i.height <= 576 and i.num_frames == 25


def test_workspace_rejects_traversal():
    with tempfile.TemporaryDirectory() as td:
        ws = VideoAIWorkspace(td)
        p = ws.root / "ok.mp4"
        p.write_bytes(b"x")
        assert ws.media_path("../../ok.mp4") == p


def test_real_mp4_encode_without_ai_model():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "smoke.mp4"
        frames = [Image.new("RGB", (320, 180), (i * 20 % 255, 40, 100)) for i in range(16)]
        meta = LocalVideoAIService._encode_mp4(frames, out, duration=1.0)
        assert out.exists() and out.stat().st_size > 1000
        # A low-FPS model timeline is physically duplicated to CFR 30 before QA.
        assert meta["source_fps"] == 16
        assert meta["target_fps"] == 30
        assert meta["frames"] == 30
        assert meta["fps"] >= 29.0
