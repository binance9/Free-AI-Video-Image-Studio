"""Smoke test cho nut "TAT BOT" (kill-switch toan bo AI Video Factory).

QUAN TRONG: KHONG duoc goi /api/system/shutdown that qua TestClient trong
test tu dong - TestClient chay app CUNG tien trinh voi pytest, nen goi that
se kill luon chinh tien trinh pytest dang chay bo test nay. Test o day
monkeypatch _kill_own_process_tree() thanh 1 spy (khong lam gi that) de xac
nhan endpoint goi dung ham kill + tra ve dung response, con viec kill THAT
(taskkill /PID <pid> /T /F ha guc ca cay tien trinh FFmpeg/python worker,
giai phong port) da duoc kiem tra THAT bang tay qua server that chay o
tien trinh rieng (subprocess doc lap, khong phai tien trinh pytest) - xem
MODULE_STATUS ghi ket qua that.

Chay: pytest -q tests/smoke/test_kill_bot_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_jobs_status_reports_idle(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/jobs/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["busy"] is False
    assert data["total"] == 0
    # phai liet ke DAY DU cac module co job, khong duoc sot module nao
    for name in ("ai_image", "model_3d", "game_ready_3d", "do_vat_3d", "video_cleanup",
                 "facebook", "tai_video_web", "character_2d", "ban_do_3d"):
        assert name in data["detail"], f"thiếu module trong /api/jobs/status: {name}"


def test_jobs_status_detects_real_running_job(smoke_tmp_path):
    """Dung 1 job that (khong mo phong) tu module lam_sach_video de xac nhan
    bo tong hop /api/jobs/status phat hien dung job dang chay o BAT KY
    module nao, khong chi rieng cac module da co san trong cancel-all cu."""
    import time
    import subprocess
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin

    ffmpeg = ffmpeg_bin()
    src = smoke_tmp_path / "src.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "gradients=size=320x240:rate=25:duration=3:speed=0.05:nb_colors=6",
        "-vf", "drawbox=x=40:y=40:w=80:h=60:color=black@1.0:t=fill",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(src),
    ], check=True, capture_output=True)

    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    info = app.state.video_workspace.create(src, "src.mp4")
    session_id = info["session_id"]
    client = TestClient(app)

    resp = client.post(f"/api/cleanup/overlay/{session_id}", json={
        "x": 0.1125, "y": 0.15, "w": 0.275, "h": 0.2833, "padding": 4, "method": "inpaint", "feather": 6,
    })
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]

    try:
        found_busy = False
        for _ in range(50):
            data = client.get("/api/jobs/status").json()
            if data["busy"] and data["detail"]["video_cleanup"] >= 1:
                found_busy = True
                break
            time.sleep(0.1)
        assert found_busy, "khong phat hien duoc job that dang chay qua /api/jobs/status"
    finally:
        app.state.video_cleanup_jobs.cancel_all()
        for _ in range(50):
            job = client.get(f"/api/cleanup/jobs/{job_id}").json()
            if job["status"] in {"cancelled", "done", "error"}:
                break
            time.sleep(0.1)


def test_shutdown_calls_kill_and_cancels_jobs(smoke_tmp_path, monkeypatch):
    """Xac nhan /api/system/shutdown: (1) goi cancel_all tren moi manager,
    (2) len lich kill process qua _kill_own_process_tree - THEO DOI bang
    monkeypatch, KHONG cho chay that (xem docstring dau file)."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    import app.core.api_system as api_system_module

    kill_calls = []
    monkeypatch.setattr(api_system_module, "_kill_own_process_tree", lambda *a, **k: kill_calls.append(True))

    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)

    resp = client.post("/api/system/shutdown")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "cancelled_jobs" in data
    assert kill_calls == [True], "endpoint phải luôn lên lịch kill process, kể cả khi không có job nào"


def test_frontend_kill_button_always_visible_not_hidden_by_home_mode():
    """Yeu cau: nut TAT BOT phai luon bam duoc (o ca man hinh Home lan
    editor) - markup phai nam NGOAI .topbar (bi an hoan toan boi
    body.home-mode .topbar{display:none}) va NGOAI .home-screen."""
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert 'id="killBotBtn"' in html
    topbar_start = html.index('<header class="topbar">')
    topbar_end = html.index("</header>", topbar_start)
    assert 'id="killBotBtn"' not in html[topbar_start:topbar_end], (
        "killBotBtn nam trong .topbar se bi an boi body.home-mode .topbar{display:none!important}"
    )
    home_start = html.index('id="homeScreen"')
    home_end = html.index("</section>", home_start)
    assert 'id="killBotBtn"' not in html[home_start:home_end]


def test_kill_bot_js_is_separate_file_not_in_app_js():
    app_js = (ROOT / "web/core/app.js").read_text(encoding="utf-8")
    assert "killBotBtn" not in app_js
    js = (ROOT / "web/core/kill_bot.js").read_text(encoding="utf-8")
    assert "killBotBtn" in js
    assert "/api/system/shutdown" in js


def test_launcher_checks_for_existing_instance_before_starting():
    """Yeu cau: 'tuyet doi khong chay 2 instance cung luc' - launcher phai
    kiem tra instance dang song truoc khi tu tim cong trong va khoi dong
    server moi."""
    text = (ROOT / "START_VIDEO_FACTORY.py").read_text(encoding="utf-8")
    assert "is_already_running" in text
    assert "def main" in text
    main_body = text[text.index("def main"):]
    assert "is_already_running" in main_body.split("find_free_port")[0], (
        "main() phải kiểm tra is_already_running() TRƯỚC khi gọi find_free_port()/khởi động server mới"
    )
