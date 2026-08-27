from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import create_app
from app.modules.model_3d_local.service import Local3DService
from app.modules.model_3d_local.triposr_backend import TripoSRBackend
from app.modules.model_3d_local.workspace import Model3DWorkspace


def _image(path: Path):
    Image.new("RGB", (512, 512), "white").save(path)


def test_triposr_status_not_installed(tmp_path):
    backend = TripoSRBackend(tmp_path / "missing", tmp_path / "cache")
    assert backend.status()["installed"] is False


def test_triposr_subprocess_contract(tmp_path):
    root = tmp_path / "project"
    tool = root / "tools" / "external" / "TripoSR"
    tool.mkdir(parents=True)
    run = tool / "run.py"
    run.write_text(
        """import argparse, pathlib
p=argparse.ArgumentParser();p.add_argument('image',nargs='+');p.add_argument('--output-dir');p.add_argument('--model-save-format');p.add_argument('--mc-resolution');p.add_argument('--device');p.add_argument('--render',action='store_true');p.add_argument('--bake-texture',action='store_true');p.add_argument('--texture-resolution');p.add_argument('--pretrained-model-name-or-path');a=p.parse_args();d=pathlib.Path(a.output_dir)/'0';d.mkdir(parents=True);(d/'mesh.glb').write_bytes(b'glTF-test');
if a.render:(d/'render.mp4').write_bytes(b'mp4-test')
""",
        encoding="utf-8",
    )
    runtime = root / "data" / "runtime3d"
    py = runtime / "venv" / ("Scripts/python.exe" if __import__('os').name == "nt" else "bin/python")
    py.parent.mkdir(parents=True)
    try:
        py.symlink_to(Path(sys.executable))
    except OSError:
        import shutil
        shutil.copy2(sys.executable, py)
    (runtime / "READY.txt").write_text("ready", encoding="utf-8")
    (runtime / "DEVICE.txt").write_text("cpu", encoding="utf-8")
    img = tmp_path / "input.png"
    _image(img)
    result = TripoSRBackend(tool, root / "data" / "models" / "3d").generate(
        img, tmp_path / "out", resolution=192, render_preview=True
    )
    assert result["model_path"].name == "mesh.glb"
    assert result["model_path"].exists()
    assert result["preview_path"].exists()


def test_workspace_keeps_3d_assets_separate(tmp_path):
    model = tmp_path / "mesh.glb"; model.write_bytes(b"mesh")
    preview = tmp_path / "preview.mp4"; preview.write_bytes(b"preview")
    ws = Model3DWorkspace(tmp_path / "assets")
    data = ws.create_asset(model, preview, {"backend":"triposr", "resolution":256})
    assert ws.model_path(data["asset_id"]).suffix == ".glb"
    assert ws.preview_path(data["asset_id"]).suffix == ".mp4"
    assert ws.metadata(data["asset_id"])["backend"] == "triposr"


def test_prompt_pipeline_uses_image_ai_then_3d(tmp_path):
    class FakeImage:
        def generate(self, prompt, style, size, quality):
            p = tmp_path / "tmp.png"; _image(p); return p.read_bytes()
    service = Local3DService(tmp_path / "tool", tmp_path / "cache", FakeImage())
    captured = {}
    def fake_generate(image_path, output_dir, **kwargs):
        captured["image"] = Path(image_path)
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        model = out / "mesh.glb"; model.write_bytes(b"mesh")
        return {"model_path":model,"preview_path":None}
    service.triposr.generate = fake_generate
    result = service.from_prompt("fantasy game hero", tmp_path / "work")
    assert captured["image"].name == "concept.png"
    assert result["model_path"].exists()


def test_3d_api_from_image(tmp_path):
    app = create_app(db_path=tmp_path / "db.sqlite", editor_dir=tmp_path / "editor")
    app.state.model_3d_workspace = Model3DWorkspace(tmp_path / "assets")
    class Fake3D:
        def status(self): return {"backend":"triposr","installed":True,"message":"ok"}
        def from_image(self, image_path, work_dir, **kwargs):
            out=Path(work_dir);out.mkdir(parents=True,exist_ok=True)
            model=out/'mesh.glb';model.write_bytes(b'mesh')
            preview=out/'render.mp4';preview.write_bytes(b'preview')
            return {"model_path":model,"preview_path":preview}
    app.state.model_3d_service = Fake3D()
    client = TestClient(app)
    img=tmp_path/'input.png';_image(img)
    with img.open('rb') as f:
        res=client.post('/api/3d/from-image', files={'file':('input.png',f,'image/png')}, data={'resolution':'256','preview':'true'})
    assert res.status_code == 200, res.text
    data=res.json()
    assert data['model_url'].startswith('/api/3d/model/')
    assert data['preview_url'].startswith('/api/3d/preview/')
    assert client.get(data['model_url']).status_code == 200


def test_ui_and_modules_are_separate():
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    appjs=(ROOT/'web/app.js').read_text(encoding='utf-8')
    assert ('data-tool="ai3d"' in html) or ('data-tool-open="ai3d"' in html)
    assert '/static/js/ai_3d.js?v=' in html
    assert '/static/js/ai_3d_viewer.js?v=' in html
    assert "ai3d:" in appjs
    assert (ROOT/'app/modules/model_3d_local/triposr_backend.py').exists()
    assert (ROOT/'app/modules/image_ai_local/service.py').exists()
    assert (ROOT/'app/modules/chinh_sua_video/service.py').exists()
