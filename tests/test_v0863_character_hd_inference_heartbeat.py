from pathlib import Path


def test_inference_has_heartbeat_and_cache_is_not_used_as_inference_watchdog():
    root = Path(__file__).resolve().parents[1]
    runner = (root / "app/modules/model_3d_local/run_character_hd.py").read_text(encoding="utf-8")
    backend = (root / "app/modules/model_3d_local/character_hd_backend.py").read_text(encoding="utf-8")
    assert "_inference_heartbeat" in runner
    assert "đang suy luận CUDA" in runner
    assert "infer_heartbeat.start()" in runner
    assert "infer_stop.set()" in runner
    assert "last_worker_activity" in backend
    assert "last_cache_growth" not in backend
    assert "không có heartbeat trong 30 phút" in backend


def test_texture_load_has_heartbeat():
    root = Path(__file__).resolve().parents[1]
    runner = (root / "app/modules/model_3d_local/run_character_hd.py").read_text(encoding="utf-8")
    assert "_texture_load_heartbeat" in runner
    assert "texture_heartbeat.start()" in runner


def test_version_is_current_0864_everywhere():
    root = Path(__file__).resolve().parents[1]
    assert 'version: str = "0.8.' in (root / "app/core/config.py").read_text(encoding="utf-8")
    assert "studio=0.8." in (root / "START_VIDEO_FACTORY.py").read_text(encoding="utf-8")
    assert "0.8.6." in (root / "web/index.html").read_text(encoding="utf-8")
