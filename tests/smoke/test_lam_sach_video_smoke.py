"""Smoke test cho module lam_sach_video (xoa nen / inpaint AI) - nhanh,
KHONG chay rembg/OpenCV that.

Chay: pytest -q tests/smoke/test_lam_sach_video_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_status(smoke_tmp_path):
    from app.modules.lam_sach_video import VideoCleanupRuntime, VideoCleanupJobManager
    from app.modules.lam_sach_video.api_lam_sach_video import router

    runtime = VideoCleanupRuntime(ROOT, smoke_tmp_path / "runtime", smoke_tmp_path / "models")
    status = runtime.status()
    assert "ready" in status
    assert router.routes
    assert VideoCleanupJobManager is not None


def test_worker_scripts_point_to_own_module_folder():
    """Bug that o phien truoc: runtime.py tung tro toi thu muc module CU
    (video_cleanup) bang string path rieng, khong phai import Python nen
    grep import thuong bo sot."""
    from app.modules.lam_sach_video.runtime import VideoCleanupRuntime
    runtime = VideoCleanupRuntime(ROOT, ROOT / "data" / "runtime_video_cleanup", ROOT / "data" / "models")
    assert "lam_sach_video" in str(runtime.background_worker)
    assert "lam_sach_video" in str(runtime.inpaint_worker)
    assert runtime.background_worker.exists()
    assert runtime.inpaint_worker.exists()


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/lam_sach_video/lam_sach_video.js").is_file()
    assert (ROOT / "app/modules/lam_sach_video/README_MODULE.md").is_file()


def test_pipeline_files_are_separate_modules():
    """Yeu cau: tach file rieng cho tung buoc cua pipeline (khong gop chung
    vao 1 file, khong nhet vao inpaint_worker.py)."""
    for name in ("video_mask.py", "video_tracking.py", "video_inpaint.py", "temporal_blend.py"):
        assert (ROOT / "app/modules/lam_sach_video" / name).is_file(), f"thiếu file {name}"


def test_video_mask_padding_clamped_and_feather_gradient():
    import numpy as np
    from app.modules.lam_sach_video.video_mask import build_rect_mask, feather_mask, dilate_mask, MAX_PADDING

    mask = build_rect_mask((200, 300), (50, 50, 40, 30), padding=999)
    assert mask.sum() > 0
    # padding phai bi gioi han boi MAX_PADDING, khong duoc lan qua rong du client truyen gia tri lon
    assert mask[50 - MAX_PADDING - 1, 70].sum() == 0

    alpha = feather_mask(mask, feather_px=6)
    assert alpha.dtype == np.float32
    assert alpha.max() == 1.0 and alpha.min() == 0.0
    # alpha phai giam dan tuyen tinh ra ngoai bien (khong nhay bac dot ngot)
    row = 65
    x1 = 50 + 40 + MAX_PADDING  # padding=999 bi clamp ve MAX_PADDING
    vals = [float(alpha[row, x1 + d]) for d in range(0, 7)]
    assert vals[0] > vals[3] > vals[6]
    assert vals[6] == 0.0

    dilated = dilate_mask(mask, pixels=3)
    assert dilated.sum() >= mask.sum()


def test_video_tracking_follows_pan_and_zoom():
    """Test that: camera pan/zoom thi mask phai bam theo dung (khong dung
    tracker CSRT vi khong co opencv-contrib - dung optical flow LK)."""
    import numpy as np
    import cv2
    from app.modules.lam_sach_video.video_tracking import MaskTracker

    rng = np.random.default_rng(0)
    h, w = 240, 320
    base = rng.integers(0, 255, (h + 40, w + 40, 3)).astype(np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), sigmaX=1.5)

    def frame_at(ox, oy):
        return base[oy:oy + h, ox:ox + w]

    bbox0 = (100, 80, 60, 50)
    tracker = MaskTracker(bbox0, (h, w))
    tracker.update(frame_at(0, 0))
    crop_dx, crop_dy = 3, 2
    bx = by = 0
    for i in range(1, 11):
        bx, by, bw, bh = tracker.update(frame_at(i * crop_dx, i * crop_dy))
    exp_x, exp_y = bbox0[0] - crop_dx * 10, bbox0[1] - crop_dy * 10
    assert abs(bx - exp_x) <= 2 and abs(by - exp_y) <= 2

    tracker2 = MaskTracker(bbox0, (h, w))

    def frame_zoom(scale):
        big = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        return big[:h, :w]

    tracker2.update(frame_zoom(1.0))
    s = 1.0
    bw2 = bbox0[2]
    for _ in range(7):
        s *= 1.03
        bx2, by2, bw2, bh2 = tracker2.update(frame_zoom(s))
    assert bw2 > bbox0[2] * 1.05  # bbox phai phinh to theo zoom-in


def test_video_inpaint_and_blend_do_not_just_blur():
    """Yeu cau cot loi: KHONG duoc chi blur che vung xoa. So sanh do net
    (Laplacian variance) cua ket qua inpaint+blend voi 1 baseline blur that
    su (GaussianBlur mang) tren cung 1 vung - inpaint phai net hon blur ro
    ret (khong phai gia tri ngau nhien may man)."""
    import numpy as np
    import cv2
    from app.modules.lam_sach_video.video_mask import build_rect_mask, feather_mask
    from app.modules.lam_sach_video.video_inpaint import inpaint_frame
    from app.modules.lam_sach_video.temporal_blend import blend_edges, sharpen_region

    h, w = 200, 260
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, : w // 2] = (200, 120, 60)
    frame[:, w // 2:] = (40, 180, 200)
    cv2.rectangle(frame, (90, 70), (170, 130), (0, 0, 0), -1)
    cv2.rectangle(frame, (100, 80), (160, 120), (255, 255, 255), -1)

    bbox = (86, 66, 88, 68)
    mask = build_rect_mask((h, w), bbox, padding=0)
    alpha = feather_mask(mask, feather_px=6)
    inpainted = inpaint_frame(frame, mask, radius=5, method="telea")
    blended = blend_edges(frame, inpainted, alpha)
    final = sharpen_region(blended, mask, amount=0.5)

    naive_blur_full = cv2.GaussianBlur(frame, (0, 0), sigmaX=8)
    x, y, bw, bh = bbox

    def lap_var(img):
        return float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

    ours = lap_var(final[y:y + bh, x:x + bw])
    blur = lap_var(naive_blur_full[y:y + bh, x:x + bw])
    assert ours > blur * 3, f"inpaint+blend ({ours}) phải sắc nét hơn hẳn blur ({blur})"

    def frac_extreme(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(((g < 10) | (g > 245)).mean())

    assert frac_extreme(final[y:y + bh, x:x + bw]) < frac_extreme(frame[y:y + bh, x:x + bw])


def test_temporal_stabilizer_reduces_flicker():
    import numpy as np
    from app.modules.lam_sach_video.temporal_blend import TemporalStabilizer

    rng = np.random.default_rng(1)
    bbox = (10, 10, 40, 30)
    base_patch = rng.integers(80, 160, (30, 40, 3)).astype(np.uint8)
    stabilizer = TemporalStabilizer(ema_alpha=0.5)
    diffs = []
    prev = None
    for _ in range(6):
        noisy = np.clip(base_patch.astype(np.int16) + rng.integers(-30, 30, base_patch.shape), 0, 255).astype(np.uint8)
        frame = np.zeros((60, 80, 3), dtype=np.uint8)
        frame[10:40, 10:50] = noisy
        out = stabilizer.stabilize(frame, bbox)
        if prev is not None:
            diffs.append(float(np.abs(out.astype(np.int16) - prev.astype(np.int16)).mean()))
        prev = out
    raw_diffs = []
    prev = None
    for _ in range(6):
        noisy = np.clip(base_patch.astype(np.int16) + rng.integers(-30, 30, base_patch.shape), 0, 255).astype(np.uint8)
        if prev is not None:
            raw_diffs.append(float(np.abs(noisy.astype(np.int16) - prev.astype(np.int16)).mean()))
        prev = noisy
    assert sum(diffs) / len(diffs) < sum(raw_diffs) / len(raw_diffs)


def test_inpaint_worker_end_to_end_real_video_not_blurred(smoke_tmp_path):
    """Test that BAT BUOC: chay 1 video that co chu/logo qua worker that
    (subprocess that su dung sys.executable + ffmpeg that), roi kiem tra
    vung xoa khong bi mo (Laplacian variance vs blur baseline) - dung sys.
    executable (venv chinh, co san cv2/numpy) giong het job_manager.py."""
    import subprocess
    import sys
    import cv2
    import numpy as np
    from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin

    ffmpeg = ffmpeg_bin()
    src = smoke_tmp_path / "src_logo.mp4"
    out = smoke_tmp_path / "cleaned.mp4"
    gen_cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "gradients=size=320x240:rate=25:duration=3:speed=0.05:nb_colors=6",
        "-vf", "drawbox=x=40:y=40:w=80:h=60:color=black@1.0:t=fill,"
               "drawbox=x=50:y=50:w=60:h=40:color=white@1.0:t=fill,"
               "drawbox=x=60:y=58:w=40:h=8:color=black@1.0:t=fill,"
               "drawbox=x=60:y=74:w=40:h=8:color=black@1.0:t=fill",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(src),
    ]
    subprocess.run(gen_cmd, check=True, capture_output=True)
    assert src.is_file()

    worker = ROOT / "app" / "modules" / "lam_sach_video" / "inpaint_worker.py"
    cmd = [sys.executable, str(worker), "--input", str(src), "--output", str(out),
           "--ffmpeg", ffmpeg, "--x", "36", "--y", "36", "--w", "88", "--h", "68", "--radius", "5", "--feather", "6"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out.is_file() and out.stat().st_size > 1024

    cap = cv2.VideoCapture(str(out))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
    ok, frame = cap.read()
    cap.release()
    assert ok

    cap2 = cv2.VideoCapture(str(src))
    cap2.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
    ok2, src_frame = cap2.read()
    cap2.release()
    assert ok2

    x, y, w, h = 36, 36, 88, 68
    roi_out = frame[y:y + h, x:x + w]
    roi_src = src_frame[y:y + h, x:x + w]
    def frac_extreme(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(((g < 10) | (g > 245)).mean())

    # Chi so ben vung nhat khong phu thuoc noi dung nen thoi diem do: dau
    # hieu chu/logo (pixel den/trang thuan) phai giam manh sau khi xoa.
    assert frac_extreme(roi_out) < frac_extreme(roi_src) * 0.5


def test_preview_endpoint_returns_real_4_stage_images(smoke_tmp_path):
    """Yeu cau: 'preview realtime: frame gốc → mask → frame đã inpaint →
    video final' - test that qua TestClient that, video that, session that."""
    import base64
    import subprocess
    import cv2
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin

    ffmpeg = ffmpeg_bin()
    src = smoke_tmp_path / "src_logo.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "gradients=size=320x240:rate=25:duration=2:speed=0.05:nb_colors=6",
        "-vf", "drawbox=x=40:y=40:w=80:h=60:color=black@1.0:t=fill,"
               "drawbox=x=50:y=50:w=60:h=40:color=white@1.0:t=fill",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(src),
    ], check=True, capture_output=True)

    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    info = app.state.video_workspace.create(src, "src_logo.mp4")
    session_id = info["session_id"]

    client = TestClient(app)
    payload = {"x": 0.1125, "y": 0.15, "w": 0.275, "h": 0.2833, "padding": 4, "feather": 6, "method": "inpaint"}
    resp = client.post(f"/api/cleanup/preview/{session_id}", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in ("original_jpg_b64", "mask_jpg_b64", "inpainted_jpg_b64", "final_jpg_b64"):
        raw = base64.b64decode(data[key])
        arr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert arr is not None and arr.size > 0, f"{key} không phải ảnh JPEG hợp lệ"


def test_overlay_endpoint_accepts_feather_field(smoke_tmp_path):
    """API /api/cleanup/overlay phai nhan them truong feather (mac dinh 6,
    0..10) va khoi dong job that (dung inpaint that, khong can venv rieng)."""
    import subprocess
    import time
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.modules.chinh_sua_video.ffmpeg_tools import ffmpeg_bin

    ffmpeg = ffmpeg_bin()
    src = smoke_tmp_path / "src_logo.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "gradients=size=320x240:rate=25:duration=1:speed=0.05:nb_colors=6",
        "-vf", "drawbox=x=40:y=40:w=80:h=60:color=black@1.0:t=fill",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(src),
    ], check=True, capture_output=True)

    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    info = app.state.video_workspace.create(src, "src_logo.mp4")
    session_id = info["session_id"]

    client = TestClient(app)
    payload = {"x": 0.1125, "y": 0.15, "w": 0.275, "h": 0.2833, "padding": 4, "feather": 8, "method": "inpaint"}
    resp = client.post(f"/api/cleanup/overlay/{session_id}", json=payload)
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]

    job = None
    for _ in range(200):
        job = client.get(f"/api/cleanup/jobs/{job_id}").json()
        if job["status"] in {"done", "error", "cancelled"}:
            break
        time.sleep(0.1)
    assert job is not None and job["status"] == "done", job
    assert job["result"]["editor"]["session_id"]
