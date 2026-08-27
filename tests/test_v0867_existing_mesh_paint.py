from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_two_step_paint_ui():
    cfg = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/ai_3d.js").read_text(encoding="utf-8")
    assert 'version: str = "0.8.9.0"' in cfg
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in html
    assert 'id="ai3dColorizeCurrent"' in html
    assert 'id="ai3dPaintMeshFile"' in html
    assert 'SETUP_CHARACTER_HD_TEXTURE.bat' in html
    assert '/api/3d/jobs/colorize' in js
    assert 'lastAssetId' in js


def test_paint_runner_is_separate_and_low_vram():
    src = (ROOT / "app/modules/nhan_vat_3d/run_character_hd_paint.py").read_text(encoding="utf-8")
    assert 'Hunyuan3DPaintPipeline.from_pretrained' in src
    assert 'enable_model_cpu_offload' in src
    assert 'validate_textured_glb' in src
    assert 'AIVF_TEXTURE_APPLIED|1' in src
    assert 'Hunyuan3DDiTFlowMatchingPipeline' not in src


def test_backend_preserves_white_mesh_on_paint_failure():
    backend = (ROOT / "app/modules/nhan_vat_3d/character_hd_backend.py").read_text(encoding="utf-8")
    jobs = (ROOT / "app/modules/nhan_vat_3d/job_manager.py").read_text(encoding="utf-8")
    assert 'def paint_existing' in backend
    assert 'TEXTURE_READY.txt' in backend
    assert 'def start_colorize' in jobs
    assert 'existing_mesh_paint' in jobs
    assert 'mesh trắng gốc' in jobs


def test_texture_setup_is_incremental():
    setup = (ROOT / "tools/install_character_hd_texture.py").read_text(encoding="utf-8")
    bat = (ROOT / "SETUP_CHARACTER_HD_TEXTURE.bat").read_text(encoding="utf-8")
    assert 'custom_rasterizer' in setup
    assert 'differentiable_renderer' in setup
    assert 'TEXTURE_READY.txt' in setup
    assert 'torchvision' not in setup
    assert 'install_character_hd_texture.py' in bat
