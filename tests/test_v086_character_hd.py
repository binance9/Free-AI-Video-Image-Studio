from pathlib import Path

from app.modules.nhan_vat_3d.character_hd_backend import CharacterHDBackend


def test_character_hd_status_isolated(tmp_path):
    backend = CharacterHDBackend(tmp_path, tmp_path / "models")
    status = backend.status()
    assert status["backend"] == "character-hd-hunyuan3d2mini"
    assert status["installed"] is False
    assert "SETUP_CHARACTER_HD.bat" in status["message"]


def test_ui_has_backend_selector_and_manual_rotation():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "modules" / "nhan_vat_3d" / "ai_3d_viewer.js").read_text(encoding="utf-8")
    ai3d = (root / "web" / "modules" / "nhan_vat_3d" / "nhan_vat_3d.js").read_text(encoding="utf-8")
    assert "0.8.6" in html
    assert 'id="ai3dBackend"' in html
    assert 'value="character_hd"' in html
    assert "SETUP_CHARACTER_HD.bat" in html
    assert "ai3dViewerRotXm" in html
    assert "ai3dViewerRotZp" in html
    assert "rotateXQuarter" in js
    assert "rotateZQuarter" in js
    assert "form.append('backend'" in ai3d


def test_character_hd_files_separated():
    root = Path(__file__).resolve().parents[1]
    assert (root / "app/modules/nhan_vat_3d/character_hd_backend.py").exists()
    assert (root / "app/modules/nhan_vat_3d/run_character_hd.py").exists()
    assert (root / "tools/install_character_hd.py").exists()
    assert (root / "SETUP_CHARACTER_HD.bat").exists()
