from pathlib import Path
from .service import AIVideoDirectorService


def test_fallback_plan_has_complete_workflow(tmp_path: Path):
    svc=AIVideoDirectorService(tmp_path)
    svc._ollama_json=lambda *a, **k: None
    p=svc.build_plan({"idea":"Nữ cung thủ bước vào thành cổ", "duration_seconds":30, "platform":"TikTok"})
    assert p["concept"]["aspect_ratio"] == "9:16"
    assert len(p["scenes"]) >= 4
    s=p["scenes"][0]
    for k in ("visual","camera","voice","caption","image_prompt","video_prompt","transition"):
        assert k in s
    assert p["edit_plan"] and p["voice_plan"] and p["caption_plan"]
    assert p["quality_policy"]["character_lock"] is True
    assert "preserve face" in p["scenes"][0]["image_prompt"].lower()


def test_patch_changes_only_selected_scene(tmp_path: Path):
    svc=AIVideoDirectorService(tmp_path)
    svc._ollama_json=lambda *a, **k: None
    p=svc.build_plan({"idea":"demo", "duration_seconds":20})
    before=p["scenes"][1]["visual"]
    p2=svc.patch_scene(p, 1, "đổi thành trời mưa")
    assert "trời mưa" in p2["scenes"][0]["visual"]
    assert p2["scenes"][1]["visual"] == before


def test_save_project_exports_json_and_shotlist(tmp_path: Path):
    svc=AIVideoDirectorService(tmp_path)
    svc._ollama_json=lambda *a, **k: None
    p=svc.build_plan({"idea":"demo save", "duration_seconds":15})
    folder=svc.save_project(p)
    assert (folder/"project.json").is_file()
    assert (folder/"shot_list.md").is_file()


def test_planned_scene_duration_fits_local_video_limit(tmp_path: Path):
    svc=AIVideoDirectorService(tmp_path)
    svc._ollama_json=lambda *a, **k: None
    p=svc.build_plan({"idea":"video 60 giây", "duration_seconds":60})
    assert max(float(s["duration"]) for s in p["scenes"]) <= 6.0


def test_auto_producer_orchestrates_scene_pipeline(tmp_path: Path, monkeypatch):
    import threading
    from types import SimpleNamespace
    import sys
    from .auto_producer import AutoProducer
    ap=sys.modules[AutoProducer.__module__]
    app=SimpleNamespace(state=SimpleNamespace())
    producer=AutoProducer(app,tmp_path)
    plan={
        "concept":{"duration_seconds":10,"aspect_ratio":"16:9","style":"cinematic","character_lock":False},
        "scenes":[
            {"id":1,"start":0,"end":5,"duration":5,"image_prompt":"a","video_prompt":"va","voice":"hello","caption":"hello"},
            {"id":2,"start":5,"end":10,"duration":5,"image_prompt":"b","video_prompt":"vb","voice":"world","caption":"world"},
        ],
        "music_plan":{"mood":"cinematic"},
    }
    class QA:
        passed=True; issues=[]
        def as_dict(self): return {"passed":True,"score":10,"checks":{},"issues":[]}
    monkeypatch.setattr(ap,"video_quality",lambda *a,**k:QA())
    def fake_image(scene,plan,out,cancel,progress,quality='balanced',anchor=None): out.write_bytes(b'png'); return {"path":str(out),"qa":QA().as_dict()}
    def fake_video(image,scene,out,cancel,progress,quality): out.write_bytes(b'mp4'); return {"path":str(out),"file":out.name,"expected_duration":5}
    def fake_norm(src,dst,ratio,fps=30,quality='balanced'): dst.write_bytes(b'norm')
    def fake_concat(clips,out): out.write_bytes(b'visual'); return out
    def fake_mix(video,voice,music,out,duration): out.write_bytes(b'final'); return out
    def fake_master(src,out,ratio,quality): out.write_bytes(b'finalmaster'); return out
    monkeypatch.setattr(producer,"_generate_scene_image",fake_image)
    monkeypatch.setattr(producer,"_generate_scene_video",fake_video)
    monkeypatch.setattr(producer,"_normalize_clip",fake_norm)
    monkeypatch.setattr(producer,"_concat",fake_concat)
    monkeypatch.setattr(producer,"_build_voice_track",lambda *a,**k: None)
    monkeypatch.setattr(producer,"_pick_music",lambda *a,**k: None)
    monkeypatch.setattr(producer,"_final_mix",fake_mix)
    monkeypatch.setattr(producer,"_final_master",fake_master)
    monkeypatch.setattr(producer,"_has_nvenc",lambda: True)
    events=[]
    result=producer.produce(plan,tmp_path/'prod',quality='final',cancel_event=threading.Event(),progress=lambda p,s,d='': events.append((p,s,d)))
    assert Path(result['final_video']).is_file()
    assert Path(result['subtitles']).is_file()
    assert len(result['scenes']) == 2
    assert result['nvenc_available'] is True
    assert result['quality'] == 'final'
    assert result['output_target'] == {"width":1920,"height":1080,"fps":30}
    assert any('VOICE_SKIPPED' in x for x in result['warnings'])


def test_character_anchor_uses_edit_reference_when_supported(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace
    import threading
    import sys
    from .auto_producer import AutoProducer
    ap=sys.modules[AutoProducer.__module__]
    class QA:
        passed=True; issues=[]
        def as_dict(self): return {"passed":True,"score":10,"checks":{},"issues":[]}
    monkeypatch.setattr(ap,"image_quality",lambda *a,**k:QA())
    calls=[]
    class ImgSvc:
        def generate(self,*a,**k): return b'x'*20000
        def edit(self,*a,**k): calls.append((a,k)); return b'y'*20000
    app=SimpleNamespace(state=SimpleNamespace(ai_image_service=ImgSvc()))
    producer=AutoProducer(app,tmp_path)
    anchor=tmp_path/'anchor.png'; anchor.write_bytes(b'a'*20000)
    out=tmp_path/'scene.png'
    plan={"concept":{"aspect_ratio":"16:9","style":"fantasy","character_lock":True}}
    scene={"image_prompt":"female archer in rain"}
    meta=producer._generate_scene_image(scene,plan,out,threading.Event(),lambda *a:None,quality='final',anchor=anchor)
    assert meta['reference_used'] is True
    assert calls and calls[0][0][0] == anchor
