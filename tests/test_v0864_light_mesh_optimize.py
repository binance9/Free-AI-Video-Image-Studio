from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_ui_toggle():
    cfg = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "web/js/ai_3d.js").read_text(encoding="utf-8")
    assert '0.8.' in cfg
    assert 'ai3dOptimizeMesh' in html
    assert "optimize_mesh" in js


def test_character_runner_has_light_optimizer_hook():
    runner = (ROOT / "app/modules/model_3d_local/run_character_hd.py").read_text(encoding="utf-8")
    backend = (ROOT / "app/modules/model_3d_local/character_hd_backend.py").read_text(encoding="utf-8")
    optimizer = (ROOT / "app/modules/model_3d_local/mesh_optimize_light.py").read_text(encoding="utf-8")
    assert '--optimize-light' in runner
    assert 'AIVF_MESH_OPTIMIZED' in runner
    assert ('optimize_mesh_light' in runner) or ('optimize_mesh_profile' in runner)
    assert 'cmd.append("--optimize-light")' in backend
    assert '0.0020' in optimizer


def test_routes_and_jobs_carry_optimize_flag():
    routes = (ROOT / "app/api/model_3d_routes.py").read_text(encoding="utf-8")
    jobs = (ROOT / "app/modules/model_3d_local/job_manager.py").read_text(encoding="utf-8")
    service = (ROOT / "app/modules/model_3d_local/service.py").read_text(encoding="utf-8")
    assert routes.count('optimize_mesh') >= 6
    assert jobs.count('optimize_mesh') >= 6
    assert service.count('optimize_mesh') >= 4
