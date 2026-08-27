from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CharacterProfile:
    name: str = "samurai_shadow"
    gender: str = "male"
    archetype: str = "fantasy assassin swordsman"
    face: str = "sharp handsome face, clear eyes, defined nose, clean mouth, visible facial features"
    hair: str = "long high ponytail"
    outfit: str = "ornate dark armor with cyan glow and purple cloth ribbons"
    weapon: str = "dual curved blades"
    palette: str = "dark blue, black, purple, cyan glow"
    render_style: str = "high-detail 2D game character illustration"
    camera: str = "full body centered sprite-friendly composition"
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        pieces = [
            self.gender,
            self.archetype,
            self.face,
            self.hair,
            self.outfit,
            self.weapon,
            self.palette,
            self.render_style,
            self.camera,
        ]
        if self.notes:
            pieces.extend(self.notes)
        return ", ".join(p.strip() for p in pieces if p and p.strip())

    @classmethod
    def from_prompt(cls, prompt: str) -> "CharacterProfile":
        prompt = (prompt or "").strip()
        if not prompt:
            return cls()
        return cls(notes=[prompt])
