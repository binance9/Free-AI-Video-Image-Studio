"""Smoke test cho module KHUNG (chua trien khai) chinh_sua_anh.

Chi kiem tra: import OK va trang thai "chua trien khai" duoc ghi ro rang.
KHONG gia vo test chuc nang chua ton tai.

Chay: pytest -q tests/smoke/test_chinh_sua_anh_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_module_imports_as_empty_scaffold():
    import app.modules.chinh_sua_anh  # noqa: F401 - phai import duoc, khong loi


def test_readme_declares_not_implemented():
    readme = (ROOT / "app/modules/chinh_sua_anh/README_MODULE.md").read_text(encoding="utf-8")
    assert "CHƯA TRIỂN KHAI" in readme


def test_no_fake_api_router_exists():
    api_files = list((ROOT / "app/modules/chinh_sua_anh").glob("api_*.py"))
    assert api_files == [], "module khung chua duoc co route that - dung bia logic"


def test_skeleton_dirs_exist():
    assert (ROOT / "app/modules/chinh_sua_anh").is_dir()
    assert (ROOT / "web/modules/chinh_sua_anh").is_dir()
