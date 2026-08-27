"""Smoke test cho module KHUNG (chua trien khai) ban_do_3d.

Chi kiem tra: import OK va trang thai "chua trien khai" duoc ghi ro rang.
KHONG gia vo test chuc nang chua ton tai.

Chay: pytest -q tests/smoke/test_ban_do_3d_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_module_imports_as_empty_scaffold():
    import app.modules.ban_do_3d  # noqa: F401 - phai import duoc, khong loi


def test_readme_declares_not_implemented():
    readme = (ROOT / "app/modules/ban_do_3d/README_MODULE.md").read_text(encoding="utf-8")
    assert "CHƯA TRIỂN KHAI" in readme


def test_no_fake_api_router_exists():
    api_files = list((ROOT / "app/modules/ban_do_3d").glob("api_*.py"))
    assert api_files == [], "module khung chua duoc co route that - dung bia logic"


def test_skeleton_dirs_exist():
    assert (ROOT / "app/modules/ban_do_3d").is_dir()
    assert (ROOT / "web/modules/ban_do_3d").is_dir()
