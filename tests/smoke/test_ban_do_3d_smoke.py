"""Smoke test cho module ban_do_3d (Bản đồ HD - tile map) - nhanh, KHONG
chay AI anh that (chi kiem tra route/contract/UI wiring).

Module nay tu "KHUNG CHUA TRIEN KHAI" da chuyen thanh "DANG DUNG THAT" (V1 HD
tile map) - xem tests/smoke/test_ban_do_3d_hd_tile_smoke.py cho hop dong
backend chi tiet hon (quality/tile/manifest).

Chay: pytest -q tests/smoke/test_ban_do_3d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_router_exists():
    from app.modules.ban_do_3d.api_ban_do_3d import router
    from app.modules.ban_do_3d.dich_vu_ban_do import Map3DService
    assert router.routes


def test_status_endpoint_returns_200(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/ban-do-3d/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert set(data.get("quality", [])) == {"lite", "standard", "final"}


def test_create_from_prompt_rejects_empty_input(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.post("/api/ban-do-3d/tao-tu-mo-ta", data={"prompt": "", "quality": "standard"})
    assert resp.status_code in (400, 422)  # 422: FastAPI treats empty Form(...) as missing; 400: our own ValueError path


def test_create_from_prompt_rejects_bad_tile_count(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.post("/api/ban-do-3d/tao-tu-mo-ta", data={"prompt": "rừng phía tây", "quality": "standard", "tile_count": "7"})
    assert resp.status_code == 400


def test_job_not_found_returns_404(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/ban-do-3d/job/khong_ton_tai")
    assert resp.status_code == 404


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/ban_do_3d/ban_do_3d.js").is_file()
    assert (ROOT / "web/modules/ban_do_3d/ban_do_3d.css").is_file()
    assert (ROOT / "app/modules/ban_do_3d/README_MODULE.md").is_file()


def test_no_separate_floating_map_frame_left_in_markup():
    """Section 1 cua yeu cau: KHONG duoc dung khung/modal rieng (mapHdModal)
    nua - phai dung chinh khung preview/viewer lon o giua (mapHdStageViewer,
    #panel-bandohd trong sidebar co san)."""
    js = (ROOT / "web/modules/ban_do_3d/ban_do_3d.js").read_text(encoding="utf-8")
    assert "mapHdModal" not in js
    assert "mapHdLauncher" not in js
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert "mapHdModal" not in html
    assert 'id="mapHdStageViewer"' in html
    assert 'id="panel-bandohd"' in html


def test_sidebar_panel_has_only_required_controls():
    """Section 2: sidebar chi giu anh mau, prompt, chat luong, so tile,
    tien trinh, nut tao map, mo map full, manifest, bat luoi tile."""
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    start = html.index('id="panel-bandohd"')
    end = html.index("MODULE: ban_do_3d END")
    panel = html[start:end]
    for required_id in (
        "mapHdImageFile", "mapHdPrompt", "map-hd-quality", "mapHdTiles",
        "mapHdProgress", "mapHdCreate", "mapHdOpenFull", "mapHdManifest", "mapHdGridToggle",
    ):
        assert required_id in panel, f"thiếu control bắt buộc trong sidebar: {required_id}"


def test_master_layout_lock_step_exists():
    """Section 3: phai co buoc khoa bo cuc tong truoc khi render tile."""
    from app.modules.ban_do_3d.khoa_bo_cuc import khoa_bo_cuc  # noqa: F401
    src = (ROOT / "app/modules/ban_do_3d/dich_vu_ban_do.py").read_text(encoding="utf-8")
    assert "khoa_bo_cuc" in src


def test_tiles_have_position_and_overlap_metadata():
    """Section 4: moi tile phai biet vi tri (row/col/neighbors/world_bbox)."""
    from app.modules.ban_do_3d.chia_o_ban_do import build_tiles
    grid = build_tiles(8, 1024, 128)
    for t in grid["tiles"]:
        assert {"row", "col", "neighbors", "world_bbox", "overlap_px"} <= t.keys()


def test_stitch_uses_real_overlap_not_edge_to_edge():
    """Section 4: stitch phai dat tile CHONG LEN nhau that (co overlap),
    khong phai canh-doi-canh - kiem tra qua kich thuoc canvas ra."""
    from app.modules.ban_do_3d.ghep_o_ban_do import stitch
    from app.modules.ban_do_3d.chia_o_ban_do import build_tiles
    import tempfile
    from PIL import Image

    grid = build_tiles(4, 128, 16)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        tile_paths = {}
        for t in grid["tiles"]:
            p = d / f"{t['tile_id']}.png"
            Image.new("RGB", (128, 128), (10, 20, 30)).save(p)
            tile_paths[t["tile_id"]] = p
        dims = stitch(tile_paths, grid, 128, d / "full.png", 16)
        # edge-to-edge would give cols*128 = 256; with real overlap it must be smaller
        assert dims["width"] < grid["cols"] * 128
        assert dims["height"] < grid["rows"] * 128
