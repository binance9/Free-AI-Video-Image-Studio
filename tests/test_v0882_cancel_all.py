from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def text(p): return (ROOT/p).read_text(encoding='utf-8')

def test_cancel_all_ui_and_route_present():
    html=text('web/index.html'); app=text('web/app.js'); main=text('app/main.py')
    assert 'id="stopAllBtn"' in html and 'id="busyStopBtn"' in html
    assert '/api/jobs/cancel-all' in app
    assert 'job_control_router' in main

def test_all_background_managers_have_cancel_all():
    for rel in [
        'app/modules/model_3d_local/job_manager.py',
        'app/modules/lam_sach_video/job_manager.py',
        'app/modules/tai_video/job_manager.py',
        'app/modules/tao_anh_ai/job_manager.py',
    ]:
        s=text(rel)
        assert 'def cancel(' in s
        assert 'def cancel_all(' in s

def test_ai_image_uses_cancellable_jobs():
    js=text('web/js/ai_image.js'); routes=text('app/modules/tao_anh_ai/api_tao_anh_ai.py')
    assert '/api/ai-image/jobs/generate' in js
    assert '/api/ai-image/jobs/edit' in js
    assert 'callback_on_step_end' in text('app/modules/tao_anh_ai/service.py')
    assert '@router.post("/ai-image/jobs/generate")' in routes

def test_3d_processes_are_cooperatively_cancelled():
    assert 'terminate_process(proc)' in text('app/modules/model_3d_local/character_hd_backend.py')
    assert 'terminate_process(proc)' in text('app/modules/model_3d_local/triposr_backend.py')
