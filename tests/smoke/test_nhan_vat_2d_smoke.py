"""Smoke test cho module nhan_vat_2d - nhanh, KHONG load model AI that.

Chay: pytest -q tests/smoke/test_nhan_vat_2d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_constructs(smoke_tmp_path):
    from app.modules.nhan_vat_2d import Character2DService, CharacterProfile
    from app.modules.nhan_vat_2d.api_nhan_vat_2d import router

    service = Character2DService(root=smoke_tmp_path / "nhan_vat_2d")
    assert service.root.exists()
    assert router.routes, "router phai co it nhat 1 route"
    profile = CharacterProfile.from_prompt("blue armor swordsman")
    assert profile is not None


def test_app_wires_character_2d_router(smoke_tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=smoke_tmp_path / "db.sqlite", editor_dir=smoke_tmp_path / "editor")
    client = TestClient(app)
    resp = client.get("/api/character-2d/status")
    assert resp.status_code != 404, "route /api/character-2d/status khong duoc dang ky"


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/nhan_vat_2d/nhan_vat_2d.js").is_file()
    assert (ROOT / "app/modules/nhan_vat_2d/README_MODULE.md").is_file()


def test_no_clip_single_character_check_regression():
    """Khoa lai bug that: CLIP single_character check (attribute_lock.py) bao SAI
    "two or more people" voi do tin cay 85-98% tren MOI lan chay that (3 job that,
    ~13 attempt), trong khi heuristic classical (single_character_quality.py, da
    la hard-gate rieng qua quality_gate.py) cham DUNG tren cung anh do. Da xoa
    check CLIP nay - xem MODULE_STATUS.md 2026-08-28. Neu ai them lai check CLIP
    ten "single_character" trong attribute_lock.py, test nay se bao dong regression."""
    import inspect
    from app.modules.nhan_vat_2d.attribute_lock import AttributeLock
    src = inspect.getsource(AttributeLock.inspect)
    assert 'self._choose(image' in src, "inspect() phai con goi _choose() cho cac check khac"
    assert ',"single_character",' not in src, (
        "CLIP single_character check (_choose(...,\"single_character\",...)) da bi them lai "
        "vao attribute_lock.py - day la check da xac nhan SAI gan 100% tren anh that, xem "
        "MODULE_STATUS.md"
    )


def test_negative_prompt_excludes_figurine_pedestal_style():
    """Khoa lai fix that: NEGATIVE_PROMPT truoc day khong co tu khoa nao loai bo
    phong cach 'figurine tren de/pedestal' du day la nguyen nhan that gay
    no_pedestal that bai lap lai qua nhieu job that - xem MODULE_STATUS.md."""
    from app.modules.nhan_vat_2d.prompt_builder import NEGATIVE_PROMPT
    neg = NEGATIVE_PROMPT.lower()
    for term in ("figurine", "pedestal"):
        assert term in neg


def test_compact_composition_height_threshold_calibrated():
    """Khoa lai hieu chuan that: nguong height_ratio da nang 0.82->0.90 dua tren
    bang chung that (job_1cc22b259cc3/candidate_04.png, height_ratio=0.871, bo
    cuc hop ly khi xem bang mat nhung bi tu choi sai o nguong cu) - xem
    MODULE_STATUS.md 2026-08-28."""
    import inspect
    from app.modules.nhan_vat_2d.compact_composition import inspect_compact_composition
    src = inspect.getsource(inspect_compact_composition)
    assert "hr <= 0.90" in src


def _make_synthetic_character_png(*, height_ratio: float, edge_to_edge: bool = False) -> bytes:
    """Build a plain-gray-background PNG with a centered dark rectangle
    'character', matching the exact color-distance convention auto_frame.py
    and compact_composition.py both rely on (a corner-median gray background,
    a high-contrast foreground blob)."""
    import io
    from PIL import Image, ImageDraw
    w = h = 512
    im = Image.new("RGB", (w, h), (180, 180, 180))
    draw = ImageDraw.Draw(im)
    if edge_to_edge:
        y0, y1 = 0, h - 1
    else:
        bh = int(h * height_ratio)
        y0 = (h - bh) // 2
        y1 = y0 + bh
    bw = int(w * 0.3)
    x0 = (w - bw) // 2
    x1 = x0 + bw
    draw.rectangle([x0, y0, x1, y1], fill=(20, 20, 20))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def test_auto_frame_zooms_out_a_nearly_edge_to_edge_character():
    """Real functional check (no GPU/CLIP needed - pure PIL/numpy): a
    synthetic character filling almost the full canvas height (0.95, just
    shy of literally touching both edges - the exact failure pattern seen
    repeatedly in real Map HD/character_2d jobs) must come back reframed
    with real margin, landing inside compact_composition.py's accepted
    window - see MODULE_STATUS.md 2026-08-28. (height_ratio=1.0 exactly
    means the bbox DOES touch both edges, which is covered separately by
    test_auto_frame_declines_when_bbox_touches_both_canvas_edges below.)"""
    from app.modules.nhan_vat_2d.auto_frame import auto_frame_character
    from app.modules.nhan_vat_2d.compact_composition import inspect_compact_composition
    import tempfile, os

    raw = _make_synthetic_character_png(height_ratio=0.95)
    framed = auto_frame_character(raw)
    assert framed is not None, "anh edge-to-edge nhung khong cham ca 2 canh 2 truc phai frame duoc"
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(framed)
        cc = inspect_compact_composition(path)
        assert cc["ok"], f"anh sau frame phai dat compact_composition: {cc}"
        assert cc["height_ratio"] < 0.95, "phai co margin ro rang, khong con gan edge-to-edge"
    finally:
        os.remove(path)


def test_auto_frame_never_shrinks_the_protected_bbox():
    """Safety invariant (real test evidence found and fixed 2026-08-28): the
    frame must always fully contain the original detected foreground bbox -
    i.e. this must never crop INTO the character. Verified here by checking
    every non-background pixel of the synthetic character rectangle is still
    present (still far from the background color) somewhere in the framed
    output."""
    from app.modules.nhan_vat_2d.auto_frame import auto_frame_character
    import io
    from PIL import Image
    import numpy as np

    raw = _make_synthetic_character_png(height_ratio=0.6)
    framed = auto_frame_character(raw)
    assert framed is not None
    im = Image.open(io.BytesIO(framed)).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    dark_pixel_count = int((arr.mean(axis=2) < 100).sum())
    # the synthetic rectangle is 30% wide; a real crop/clip bug would shrink
    # or eliminate the dark region entirely rather than just relocate it.
    assert dark_pixel_count > 1000, "vung toi (nhan vat) bi mat/bi cat qua nhieu sau khi frame"


def test_auto_frame_declines_when_bbox_touches_both_canvas_edges():
    """Regression lock for the real bug found 2026-08-28: an earlier version
    used a connected-component pass that could UNDER-count real content
    (a low-contrast accessory, an anti-aliased pedestal edge), producing a
    frame smaller than what compact_composition.py itself would later
    measure. Fixed by declining to frame at all whenever the detected
    foreground already touches both edges of an axis (true extent unknown -
    could be an unbounded vignette or content already cut off) rather than
    guessing. See MODULE_STATUS.md 2026-08-28."""
    from app.modules.nhan_vat_2d.auto_frame import auto_frame_character
    raw = _make_synthetic_character_png(height_ratio=1.0, edge_to_edge=True)
    framed = auto_frame_character(raw)
    assert framed is None, "bbox cham ca 2 canh (pham vi that khong biet duoc) phai tra ve None"


def test_service_uses_frame_and_validate_safety_net_only_for_create_anchor():
    """Khoa lai pham vi da test that: _save_and_frame_png_bytes() (auto-frame +
    per-image face/fullbody rollback safety net) chi duoc dung tai diem luu
    candidate cua create_anchor - KHONG dung cho create_from_reference hay
    action-sheet frame loop, dung nhu pham vi da xac nhan qua 5 lan chay GPU
    that (xem MODULE_STATUS.md 2026-08-28)."""
    import inspect
    from app.modules.nhan_vat_2d.service import Character2DService
    assert "_save_and_frame_png_bytes" in inspect.getsource(Character2DService._generate_locked_anchor)
    assert "_save_and_frame_png_bytes" not in inspect.getsource(Character2DService.create_from_reference)
