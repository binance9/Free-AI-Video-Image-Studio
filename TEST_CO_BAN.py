from pathlib import Path
import json, tempfile
from maintenance import SystemMaintenance
from tools import ComputerTools, ToolError

base=Path(__file__).resolve().parent
cfg=json.loads((base/"config.json").read_text(encoding="utf-8"))
m=SystemMaintenance(cfg)
assert "TÌNH TRẠNG MÁY" in m.health_report()
assert "QUÉT RÁC" in m.scan_report()
assert "GPU / CUDA" in m.check_cuda() or "Torch runtime: FAIL" in m.check_cuda()

t=ComputerTools(cfg,confirm_callback=lambda a,b:False)
assert "TÌNH TRẠNG MÁY" in t.execute("maintenance_report",{})
assert "QUÉT RÁC" in t.execute("scan_junk",{})
try:
    t.execute("run_shell",{})
    raise AssertionError("run_shell phải bị khóa")
except ToolError:
    pass
print("GA MAINTENANCE BASIC TEST: PASS")
