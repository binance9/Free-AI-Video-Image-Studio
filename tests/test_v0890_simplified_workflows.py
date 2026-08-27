from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(p): return (ROOT/p).read_text(encoding="utf-8")
def test_cleanup_is_integrated_and_one_action():
    h=text("web/index.html"); j=text("web/modules/lam_sach_video/lam_sach_video.js"); a=text("web/core/app.js")
    assert "DỌN VIDEO AI" in h
    assert 'id="cleanupModeBg"' in h and 'id="cleanupModeErase"' in h
    assert "XÓA NỀN NGAY" in h and "⌫ XÓA NGAY" in h
    assert "if(name==='erase') name='bgremove'" in a
    assert "setCleanupMode" in j

def test_3d_simple_flow_hides_technical_choices():
    h=text("web/index.html"); j=text("web/modules/nhan_vat_3d/nhan_vat_3d.js")
    assert 'id="ai3dSimpleRun"' in h and "TẠO MODEL 3D" in h
    assert 'id="ai3dSimpleQuality"' in h and 'id="ai3dAdvanced"' in h
    assert "applySimpleQuality" in j and "autoPaintAfterShape" in j
    assert "setTimeout(()=>$('ai3dColorizeCurrent')?.click()" in j

def test_outputs_and_recent_project_are_easy_to_find():
    h=text("web/index.html"); a=text("web/core/app.js"); home=text("web/core/home_screen.js"); main=text("app/main.py")
    assert 'id="openResultsBtn"' in h and "💾 LƯU VIDEO" in h
    assert "/api/system/open-folder?kind=editor" in a
    assert "aivf_recent_video" in a and "restoreSession" in a and "homeRecentOpen" in home
    assert "system_router" in main

def test_3d_fast_preset_really_uses_light_backend():
    j=text("web/modules/nhan_vat_3d/nhan_vat_3d.js"); h=text("web/index.html")
    assert "fast:{backend:'quick',resolution:'192',profile:'light'}" in j
    assert "balanced:{backend:'character_hd',resolution:'256',profile:'medium'}" in j
    assert "best:{backend:'character_hd',resolution:'256',profile:'hd'}" in j
    assert "Nhanh · TripoSR · nhẹ máy" in h
