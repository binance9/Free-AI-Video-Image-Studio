from __future__ import annotations

import io
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.modules.image_ai_local.upscale import generation_dimensions, target_dimensions
from app.modules.am_nhac import LocalMusicLibrary
from app.modules.chinh_sua_video.ffmpeg_tools import run_tool
from app.modules.chinh_sua_video.probe import probe_video


def make_video(path: Path, seconds: float = 3.0, size: str = "640x360", audio: bool = True):
    args = [
        "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=0x203050:s={size}:d={seconds}:r=24",
    ]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac"]
    args += [str(path)]
    run_tool(args)


def make_music(path: Path, seconds: float = 6.0):
    run_tool([
        "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=660:duration={seconds}",
        "-c:a", "pcm_s16le", str(path),
    ])


def test_free_local_policy_and_health():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        app = create_app(db_path=root / "db.sqlite", editor_dir=root / "sessions")
        app.state.model_dir = root / "models"
        client = TestClient(app)
        assert client.get("/api/health").json()["status"] == "ok"
        status = client.get("/api/settings/local-ai").json()
        assert status["free_local"] is True
        assert status["paid_api_required"] is False
        req = (Path(__file__).parents[1] / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "openai" not in req and "jamendo" not in req


def test_editor_cut_merge_render_and_music():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        app = create_app(db_path=root / "db.sqlite", editor_dir=root / "sessions")
        app.state.music_library = LocalMusicLibrary(root / "music_library")
        client = TestClient(app)

        video = root / "src.mp4"
        make_video(video, 3.0)
        with open(video, "rb") as f:
            up = client.post("/api/editor/upload", files={"file": ("src.mp4", f, "video/mp4")})
        assert up.status_code == 200, up.text
        sid = up.json()["session_id"]

        cut = client.post(f"/api/editor/{sid}/cut", json={"start": 0.2, "end": 2.4})
        assert cut.status_code == 200, cut.text
        assert 2.0 <= cut.json()["duration"] <= 2.5

        extra = root / "extra.mp4"
        make_video(extra, 1.0, size="854x480", audio=False)
        with open(extra, "rb") as f:
            merged = client.post(
                f"/api/editor/{sid}/append",
                files={"file": ("extra.mp4", f, "video/mp4")},
                data={"position": "after"},
            )
        assert merged.status_code == 200, merged.text
        assert merged.json()["duration"] >= 3.0

        payload = {"layers": [{
            "id": "t1", "type": "text", "text": "Xin chào", "x": 0.5, "y": 0.8,
            "width_ratio": 0.3, "start": 0, "end": 1.5, "font_size_ratio": 0.06,
            "color": "#ffffff", "outline_color": "#000000", "outline_width": 4,
            "background": "#000000", "background_opacity": 0.2, "font_family": "segoe",
            "shadow_color": "#000000", "shadow_opacity": 0.4, "shadow_blur": 4,
        }]}
        rendered = client.post(f"/api/editor/{sid}/render", json=payload)
        assert rendered.status_code == 200, rendered.text
        assert len(rendered.content) > 1000

        music = root / "gaming_fast.wav"
        make_music(music)
        with open(music, "rb") as f:
            mu = client.post(f"/api/editor/{sid}/music/upload", files={"file": (music.name, f, "audio/wav")})
        assert mu.status_code == 200, mu.text
        audio_id = mu.json()["audio_id"]
        found = client.post("/api/music/search", json={"wish": "gaming nhanh", "limit": 10})
        assert found.status_code == 200, found.text
        assert any("gaming" in item["name"] for item in found.json()["items"])
        mixed = client.post(f"/api/editor/{sid}/music/apply", json={
            "audio_id": audio_id, "clip_duration": 2, "insert_at": 0,
            "volume": 0.25, "keep_original": True, "smart_excerpt": True,
        })
        assert mixed.status_code == 200, mixed.text
        assert probe_video(app.state.video_workspace.current_path(sid)).has_audio


def test_caption_and_translation_routes_with_local_service_contracts():
    class CaptionFake:
        def transcribe(self, _path):
            return {"text": "Xin chào", "segments": [{"start": 0.0, "end": 1.0, "text": "Xin chào"}], "language": "vi", "engine": "fake-local"}

    class TranslateFake:
        def translate_segments(self, segments, source, target):
            assert source == "vi" and target == "English"
            return [{**segments[0], "text": "Hello"}]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        app = create_app(db_path=root / "db.sqlite", editor_dir=root / "sessions")
        app.state.caption_service = CaptionFake()
        app.state.translation_service = TranslateFake()
        client = TestClient(app)
        video = root / "src.mp4"; make_video(video, 2.0)
        with open(video, "rb") as f:
            sid = client.post("/api/editor/upload", files={"file": ("src.mp4", f, "video/mp4")}).json()["session_id"]
        tr = client.post(f"/api/editor/{sid}/captions/transcribe")
        assert tr.status_code == 200 and tr.json()["language"] == "vi"
        tt = client.post("/api/captions/translate", json={
            "segments": tr.json()["segments"], "source_language": "vi", "target_language": "English"
        })
        assert tt.status_code == 200 and tt.json()["segments"][0]["text"] == "Hello"


def test_ai_image_routes_without_external_api():
    class ImageFake:
        def generate(self, prompt, style, size, quality):
            out = io.BytesIO(); Image.new("RGB", (128, 96), "navy").save(out, "PNG"); return out.getvalue()
        def edit(self, image_path, prompt, style, size, quality):
            out = io.BytesIO(); Image.new("RGB", (96, 128), "green").save(out, "PNG"); return out.getvalue()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        app = create_app(db_path=root / "db.sqlite", editor_dir=root / "sessions")
        app.state.ai_image_service = ImageFake()
        app.state.ai_image_workspace.root = root / "ai_images"
        app.state.ai_image_workspace.root.mkdir(parents=True, exist_ok=True)
        client = TestClient(app)
        gen = client.post("/api/ai-image/generate", json={"prompt": "rừng fantasy", "style": "fantasy", "size": "2048x1152", "quality": "medium"})
        assert gen.status_code == 200, gen.text
        assert client.get(gen.json()["url"]).status_code == 200
        src = root / "ref.png"; Image.new("RGB", (64, 64), "red").save(src)
        with open(src, "rb") as f:
            edit = client.post("/api/ai-image/edit", files={"file": ("ref.png", f, "image/png")}, data={"prompt": "hoạt hình", "style": "cartoon3d", "size": "1024x1024", "quality": "medium"})
        assert edit.status_code == 200, edit.text


def test_image_size_helpers_and_source_isolation():
    assert generation_dimensions("3840x2160") == (640, 384)
    assert generation_dimensions("2160x3840") == (384, 640)
    assert target_dimensions("2048x2048") == (2048, 2048)
    root = Path(__file__).parents[1]
    app_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in (root / "app").rglob("*.py"))
    assert "from openai" not in app_text.lower()
    assert "import openai" not in app_text.lower()
    assert "jamendoclient" not in app_text.lower()
