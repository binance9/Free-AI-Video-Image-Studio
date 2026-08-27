from pathlib import Path


def test_character_hd_timeout_is_progress_aware():
    root = Path(__file__).resolve().parents[1]
    text = (root / "app/modules/model_3d_local/character_hd_backend.py").read_text(encoding="utf-8")
    assert "timeout_seconds=14400" in text
    assert "idle_timeout_seconds=1800" in text
    assert "last_worker_activity" in text
    assert "heartbeat" in text
    assert "30 phút" in text
    assert "4 giờ" in text
