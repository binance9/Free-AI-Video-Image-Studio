from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_paint_trust_local_custom_pipeline_patch():
    text = (ROOT / "app/modules/nhan_vat_3d/run_character_hd_paint.py").read_text(encoding="utf-8")
    assert "_enable_local_hunyuan_custom_pipeline" in text
    assert 'kwargs.setdefault("trust_remote_code", True)' in text
    assert 'local_custom' in text and 'Path(str(custom_pipeline)).exists()' in text
    assert "Cho phép pipeline Paint local" in text

def test_custom_chick_pack_has_24_pngs_and_ui_tab():
    stickers = ROOT / "web/stickers"
    files = sorted(stickers.glob("ga_*.png"))
    assert len(files) == 24
    assert all(p.stat().st_size > 5000 for p in files)
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/core/app.js").read_text(encoding="utf-8")
    emoji = (ROOT / "web/modules/chinh_sua_video/emoji_picker.js").read_text(encoding="utf-8")
    assert 'data-sticker-tab="custom"' in html
    assert 'id="customStickerGrid"' in html
    assert "const customStickers =" in js
    assert "stickerCustom" in emoji
