from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "app/main.py"
DESKTOP = ROOT / "AI_VIDEO_FACTORY_DESKTOP.py"
FRESHNESS = ROOT / "app/core/local_freshness.py"

main_text = MAIN.read_text(encoding="utf-8")
if "from app.core.local_freshness import install_local_freshness" not in main_text:
    raise SystemExit("VERIFY FAIL: local_freshness import missing from app/main.py")
if "install_local_freshness(app)" not in main_text:
    raise SystemExit("VERIFY FAIL: local freshness middleware is not installed")

spec = importlib.util.spec_from_file_location("aivf_desktop_verify", DESKTOP)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory(prefix="aivf_fresh_verify_") as td:
    root = Path(td)
    (root / "app").mkdir()
    (root / "web").mkdir()
    (root / "app/test.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "web/test.js").write_text("window.VALUE = 1;\n", encoding="utf-8")

    first = module.source_fingerprint(root)
    second = module.source_fingerprint(root)
    if first != second:
        raise SystemExit("VERIFY FAIL: fingerprint is not deterministic")

    (root / "web/test.js").write_text("window.VALUE = 2;\n", encoding="utf-8")
    changed = module.source_fingerprint(root)
    if first["sha256"] == changed["sha256"]:
        raise SystemExit("VERIFY FAIL: edited UI file did not change fingerprint")

    if not module.needs_refresh(first, changed):
        raise SystemExit("VERIFY FAIL: edited source does not request refresh")
    if module.needs_refresh(changed, changed):
        raise SystemExit("VERIFY FAIL: unchanged source incorrectly requests refresh")
    if not module.needs_refresh(changed, changed, restart_requested=True):
        raise SystemExit("VERIFY FAIL: restart.request is ignored")

for marker in ("/api/jobs/status", "/api/system/shutdown", "clear_python_cache", "--app=", "source_fingerprint"):
    if marker not in DESKTOP.read_text(encoding="utf-8"):
        raise SystemExit(f"VERIFY FAIL: desktop launcher missing guard {marker}")

if "no-store, no-cache, must-revalidate" not in FRESHNESS.read_text(encoding="utf-8"):
    raise SystemExit("VERIFY FAIL: static no-cache policy missing")

print("DESKTOP_AUTO_FRESH_V6_5_9_VERIFY: PASS")
