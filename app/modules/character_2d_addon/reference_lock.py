from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class ReferenceChoice:
    enabled: bool
    key: str | None
    path: str | None
    reason: str
    strength: float = 0.30
    strict: bool = False


class ReferenceLibrary:
    """Local reference bank for strict compact character locking.

    V12.2 treats an approved reference as the structural source of truth.
    When the requested spec matches the approved male swordsman attributes,
    denoising is intentionally kept low so gender, weapon class, armor layout,
    chibi proportions and framing are preserved instead of being reinvented.
    """

    def __init__(self, module_dir: str | Path | None = None):
        base = Path(module_dir or Path(__file__).resolve().parent)
        self.template_dir = base / "templates"

    @staticmethod
    def _matches_strict_male_swordsman(spec) -> bool:
        return (
            getattr(spec, "gender", None) == "male"
            and getattr(spec, "weapon_type", None) in {"sword", "katana", "blade"}
            and getattr(spec, "weapon_count", None) in {None, 1}
            and getattr(spec, "armor_primary", None) in {None, "blue"}
            and getattr(spec, "accent_color", None) in {None, "purple"}
            and getattr(spec, "hair_color", None) in {None, "dark", "black"}
            and getattr(spec, "hair_length", None) in {None, "long"}
        )

    def choose(self, spec) -> ReferenceChoice:
        preset = getattr(spec, "render_preset", "compact_game")
        gender = getattr(spec, "gender", None)
        weapon = getattr(spec, "weapon_type", None)
        if preset != "compact_game":
            return ReferenceChoice(False, None, None, "preset_not_compact")

        if gender == "male" and weapon in {"sword", "katana", "blade"}:
            path = self.template_dir / "compact_male_swordsman.png"
            if path.is_file():
                if self._matches_strict_male_swordsman(spec):
                    return ReferenceChoice(
                        True, "compact_male_swordsman", str(path),
                        "strict_exact_reference_match", 0.26, True,
                    )
                return ReferenceChoice(
                    True, "compact_male_swordsman", str(path),
                    "matched_gender_weapon", 0.38, False,
                )
        return ReferenceChoice(False, None, None, "no_matching_reference")

    def info(self, spec) -> dict:
        return asdict(self.choose(spec))
