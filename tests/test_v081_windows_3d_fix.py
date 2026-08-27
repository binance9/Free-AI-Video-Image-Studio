from pathlib import Path
from app.modules.nhan_vat_3d.triposr_backend import TripoSRBackend

def test_isolated_runtime_path(tmp_path):
    root = tmp_path / "p"
    tool = root / "tools" / "external" / "TripoSR"
    tool.mkdir(parents=True)
    b = TripoSRBackend(tool, root / "data" / "models" / "3d")
    s = str(b.runtime_python).lower()
    assert "runtime3d" in s
    assert "venv" in s
