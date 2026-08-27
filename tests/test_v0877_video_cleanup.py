from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_version_0877_and_separate_modules():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')
    assert (ROOT/'app/modules/lam_sach_video/background_worker.py').is_file()
    assert (ROOT/'app/modules/lam_sach_video/inpaint_worker.py').is_file()
    assert (ROOT/'app/modules/lam_sach_video/api_lam_sach_video.py').is_file()


def test_cleanup_ui_has_both_tools_and_shared_progress():
    html=text('web/index.html'); js=text('web/js/video_cleanup.js')
    assert ('data-tool="bgremove"' in html) or ('data-tool-open="bgremove"' in html)
    assert 'id="cleanupModeErase"' in html
    assert 'XÓA NỀN NGAY' in html
    assert 'Xóa chữ / logo / vật thể' in html
    assert 'cleanupMask' in html
    assert 'S.updateBusyProgress?.' in js
    assert '/api/cleanup/background/' in js
    assert '/api/cleanup/overlay/' in js
    assert '/api/cleanup/jobs/' in js


def test_cleanup_runtime_is_isolated_and_setup_is_explicit():
    setup=text('tools/install_video_cleanup.py')
    req=text('requirements_video_cleanup.txt')
    bat=text('SETUP_VIDEO_CLEANUP_AI.bat')
    assert 'runtime_video_cleanup' in setup
    assert 'onnxruntime-gpu>=1.19,<1.27' in req
    assert 'rembg' in req and 'opencv-python-headless' in req
    assert 'install_video_cleanup.py' in bat


def test_transparent_versions_preserve_webm_suffix():
    workspace=text('app/modules/chinh_sua_video/workspace.py')
    routes=text('app/modules/chinh_sua_video/api_chinh_sua_video.py')
    assert 'suffix = generated_path.suffix.lower() or ".mp4"' in workspace
    assert '".webm": "video/webm"' in routes


def test_overlay_modes_and_background_models_are_validated():
    routes=text('app/modules/lam_sach_video/api_lam_sach_video.py')
    jobs=text('app/modules/lam_sach_video/job_manager.py')
    assert '^(transparent|solid)$' in routes
    assert '^(delogo|inpaint)$' in routes
    assert 'u2net_human_seg' in jobs
    assert 'isnet-general-use' in jobs
    assert 'delogo=x=' in jobs
