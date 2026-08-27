from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_mesh_profile_ui():
    cfg = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/ai_3d.js").read_text(encoding="utf-8")
    assert 'version: str = "0.8.9.0"' in cfg
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in html
    assert 'id="ai3dMeshProfile"' in html
    assert 'value="hd" selected' in html
    assert 'value="medium"' in html
    assert 'value="light"' in html
    assert "mesh_profile" in js


def test_mesh_profiles_are_isolated_and_calibrated():
    src = (ROOT / "app/modules/nhan_vat_3d/mesh_optimize_profiles.py").read_text(encoding="utf-8")
    assert '"hd"' in src and '0.0020' in src
    assert '"medium"' in src and '0.0042' in src
    assert '"light"' in src and '0.0065' in src
    assert 'optimize_mesh_profile' in src


def test_backend_route_and_jobs_carry_mesh_profile():
    backend = (ROOT / "app/modules/nhan_vat_3d/character_hd_backend.py").read_text(encoding="utf-8")
    runner = (ROOT / "app/modules/nhan_vat_3d/run_character_hd.py").read_text(encoding="utf-8")
    routes = (ROOT / "app/modules/nhan_vat_3d/api_nhan_vat_3d.py").read_text(encoding="utf-8")
    jobs = (ROOT / "app/modules/nhan_vat_3d/job_manager.py").read_text(encoding="utf-8")
    assert '"--mesh-profile"' in backend
    assert 'choices=("hd", "medium", "light")' in runner
    assert routes.count("mesh_profile") >= 8
    assert jobs.count("mesh_profile") >= 6


def test_default_preset_stays_safe_hd_shape_only():
    js = (ROOT / "web/js/ai_3d_presets.js").read_text(encoding="utf-8")
    assert "texture: false, optimize: true, mesh: 'hd'" in js
    assert "aivf3dPresetV0867" in js
