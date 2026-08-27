from pathlib import Path
from app.modules.model_3d_local.triposr_backend import TripoSRBackend


def test_progress_stage_map(tmp_path):
    root = tmp_path / "p"
    tool = root / "tools" / "external" / "TripoSR"
    tool.mkdir(parents=True)
    b = TripoSRBackend(tool, root / "data" / "models" / "3d")
    assert any(item[0] == "Initializing model" for item in b.STAGES)
    assert any(item[0] == "Extracting mesh" for item in b.STAGES)


def test_snapshot_discovery(tmp_path):
    root = tmp_path / "p"
    tool = root / "tools" / "external" / "TripoSR"
    tool.mkdir(parents=True)
    cache = root / "data" / "models" / "3d"
    snap = cache / "hub" / "models--stabilityai--TripoSR" / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "model.ckpt").write_bytes(b"x")
    b = TripoSRBackend(tool, cache)
    assert b._snapshot("stabilityai", "TripoSR", "model.ckpt") == snap.resolve()
