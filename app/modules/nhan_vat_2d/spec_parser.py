from __future__ import annotations

from dataclasses import dataclass, asdict
import re

COLORS = ("burgundy","crimson","maroon","navy","emerald","blue","purple","red","green","black","white","silver","gold","brown","gray","grey","cyan","dark")
WEAPONS = ("sword","katana","blade","axe","spear","bow","staff","hammer","shield","dagger","knife","gun","rifle")

@dataclass(slots=True)
class CharacterSpec:
    raw_prompt: str
    gender: str | None = None
    weapon_type: str | None = None
    weapon_count: int | None = None
    armor_primary: str | None = None
    accent_color: str | None = None
    cape_color: str | None = None
    hair_color: str | None = None
    hair_length: str | None = None
    full_body: bool = True
    single_character: bool = True
    plain_background: bool = True
    render_preset: str = "compact_game"

    def to_dict(self) -> dict:
        return asdict(self)


def _first_color_near(text: str, noun: str) -> str | None:
    low=text.lower()
    for c in COLORS:
        if re.search(rf"\b{c}\b[^,;]{{0,20}}\b{re.escape(noun)}\b", low) or re.search(rf"\b{re.escape(noun)}\b[^,;]{{0,20}}\b{c}\b", low):
            aliases = {"grey":"gray", "burgundy":"red", "crimson":"red", "maroon":"red", "navy":"blue", "emerald":"green"}
            return aliases.get(c, c)
    return None


def parse_character_spec(prompt: str) -> CharacterSpec:
    raw=" ".join((prompt or "").split())
    low=raw.lower()
    gender=None
    if re.search(r"\b(male|man|boy)\b", low): gender="male"
    elif re.search(r"\b(female|woman|girl)\b", low): gender="female"

    weapon_type=next((w for w in WEAPONS if re.search(rf"\b{w}\b", low)), None)
    count=None
    if weapon_type:
        if re.search(rf"\b(one|single|1)\b[^,;]{{0,30}}\b{weapon_type}s?\b", low): count=1
        elif re.search(rf"\b(two|dual|2)\b[^,;]{{0,30}}\b{weapon_type}s?\b", low): count=2

    armor=_first_color_near(low, "armor") or _first_color_near(low, "armour")
    accent=_first_color_near(low, "sash") or _first_color_near(low, "belt") or _first_color_near(low, "cloth")
    # Recolor phrasing often gives two armor colors, e.g. "burgundy red and gold".
    # Treat the second color as the armor accent when no sash/belt color was supplied.
    if accent is None and armor:
        if re.search(r"\b(?:burgundy|crimson|maroon|red)\b[^,;]{0,18}\band\s+gold\b", low):
            accent = "gold"
        elif re.search(r"\bblue\b[^,;]{0,18}\band\s+(?:gold|purple)\b", low):
            accent = "gold" if "gold" in low else "purple"
    cape_color=_first_color_near(low, "cape") or _first_color_near(low, "cloak")
    hair_color=_first_color_near(low, "hair")
    hair_length="long" if re.search(r"\blong\b[^,;]{0,15}\bhair\b|\bhair\b[^,;]{0,15}\blong\b", low) else None
    if re.search(r"\bshort\b[^,;]{0,15}\bhair\b|\bhair\b[^,;]{0,15}\bshort\b", low): hair_length="short"

    return CharacterSpec(raw_prompt=raw, gender=gender, weapon_type=weapon_type, weapon_count=count,
                         armor_primary=armor, accent_color=accent, cape_color=cape_color, hair_color=hair_color, hair_length=hair_length)
