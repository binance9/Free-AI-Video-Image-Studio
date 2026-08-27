"""Free local subtitle translation via Argos Translate packages."""
from __future__ import annotations

_LANGUAGE_ALIASES = {
    "Vietnamese": "vi", "English": "en", "Japanese": "ja", "Korean": "ko",
    "Chinese": "zh", "Thai": "th", "Spanish": "es", "French": "fr",
    "vi": "vi", "en": "en", "ja": "ja", "ko": "ko", "zh": "zh", "th": "th", "es": "es", "fr": "fr",
}


class LocalTranslationService:
    def translate_segments(self, segments: list[dict], source_language: str, target_language: str) -> list[dict]:
        source = self._code(source_language)
        target = self._code(target_language)
        if source == target:
            return [dict(row) for row in segments]
        self._ensure_translation(source, target)
        import argostranslate.translate
        translated = []
        for row in segments:
            translated.append({**row, "text": argostranslate.translate.translate(str(row.get("text", "")), source, target)})
        return translated

    def _ensure_translation(self, source: str, target: str) -> None:
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError as exc:
            raise ValueError("Chưa cài bộ dịch local. Chạy SETUP_FREE_AI.bat một lần.") from exc
        if self._has_pair(source, target):
            return
        try:
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
        except Exception as exc:
            raise ValueError("Thiếu model dịch local và hiện không tải được Internet.") from exc
        direct = next((p for p in available if p.from_code == source and p.to_code == target), None)
        if direct:
            argostranslate.package.install_from_path(direct.download())
            return
        if source != "en" and target != "en":
            first = next((p for p in available if p.from_code == source and p.to_code == "en"), None)
            second = next((p for p in available if p.from_code == "en" and p.to_code == target), None)
            if first and second:
                if not self._has_pair(source, "en"):
                    argostranslate.package.install_from_path(first.download())
                if not self._has_pair("en", target):
                    argostranslate.package.install_from_path(second.download())
                return
        raise ValueError(f"Chưa có model dịch miễn phí {source} → {target}")

    @staticmethod
    def _has_pair(source: str, target: str) -> bool:
        import argostranslate.translate
        try:
            return argostranslate.translate.get_translation_from_codes(source, target) is not None
        except Exception:
            return False

    @staticmethod
    def _code(value: str) -> str:
        code = _LANGUAGE_ALIASES.get((value or "").strip())
        if not code:
            raise ValueError("Ngôn ngữ dịch chưa được hỗ trợ")
        return code
