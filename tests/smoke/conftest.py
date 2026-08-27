"""Smoke tests dung thu muc rieng duoi data/_smoke_tmp/ thay vi tmp_path
cua pytest, vi tmp_path (OS temp qua AppData/Local/Temp) bi PermissionError
tren may Windows nay (van de moi truong co san, khong lien quan refactor -
xem cac loi PermissionError tuong tu trong baseline pytest o test_v08_3d.py,
test_v081_windows_3d_fix.py...). data/_smoke_tmp/ nam trong data/ da duoc
gitignore san.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE_TMP_ROOT = ROOT / "data" / "_smoke_tmp"


@pytest.fixture
def smoke_tmp_path():
    folder = SMOKE_TMP_ROOT / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
