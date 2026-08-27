"""Smoke test cho module phu_de (caption + dich thuat) - nhanh,
KHONG load Whisper model that.

Chay: pytest -q tests/smoke/test_phu_de_smoke.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_imports_and_constructs(smoke_tmp_path):
    from app.modules.phu_de import extract_audio, LocalCaptionService, LocalTranslationService
    from app.modules.phu_de.api_phu_de import router

    caption_service = LocalCaptionService("small", smoke_tmp_path / "whisper")
    assert caption_service._model is None, "constructor khong duoc load Whisper model ngay"
    translation_service = LocalTranslationService()
    assert translation_service is not None
    assert extract_audio is not None
    assert router.routes


def test_translate_local_merged_as_dich_thuat():
    from app.modules.phu_de.dich_thuat import LocalTranslationService
    assert LocalTranslationService is not None


def test_frontend_assets_exist():
    assert (ROOT / "web/modules/phu_de/phu_de.js").is_file()
    assert (ROOT / "app/modules/phu_de/README_MODULE.md").is_file()
