from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_version_0869():
    assert 'version: str = "0.8.9.0"' in text('app/core/config.py')
    assert 'FREE LOCAL STUDIO · 0.8.9.0' in text('web/index.html')
    assert 'studio=0.8.9.0' in text('START_VIDEO_FACTORY.py')


def test_shared_progress_ui_is_present():
    html = text('web/index.html')
    for marker in ['busyPct', 'busyBar', 'busyDetail', 'busyElapsed', 'task_progress.js?v=0878']:
        assert marker in html
    js = text('web/js/task_progress.js')
    assert 'class TaskProgress' in js
    assert "this.mode = 'auto'" in js
    assert 'return Math.min(94' in js
    assert 'finish(stage = \'Hoàn tất\'' in js


def test_studio_exports_shared_progress_hooks():
    js = text('web/app.js')
    assert 'function updateBusyProgress' in js
    assert 'function failBusyProgress' in js
    assert 'updateBusyProgress,failBusyProgress' in js
    assert "taskProgress?.start" in js


def test_real_job_modules_mirror_progress():
    fb = text('web/js/facebook_video.js')
    d3 = text('web/js/ai_3d.js')
    assert 'S.updateBusyProgress?.(value' in fb
    assert "S.setBusy(true, 'Tải video từ Facebook'" in fb
    assert 'S.updateBusyProgress?.(p' in d3
    assert 'S.setBusy(true, busyText, modeText)' in d3


def test_legacy_long_actions_inherit_progress():
    captions = text('web/js/captions.js')
    image = text('web/js/ai_image.js')
    music = text('web/js/music.js')
    app = text('web/app.js')
    assert captions.count('S.setBusy(true') >= 2
    assert image.count('S.setBusy(true') >= 2
    assert music.count('S.setBusy(true') >= 3
    for label in ['Đang cắt video', 'Đang ghép video', 'Đang render video hoàn chỉnh']:
        assert label in app


def test_local_ai_install_uses_same_progress():
    js = text('web/js/settings.js')
    assert 'S.updateBusyProgress?.' in js
    assert "S.setBusy(true,'Đang cài AI local'" in js
