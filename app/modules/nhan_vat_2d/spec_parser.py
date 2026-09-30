from __future__ import annotations

from dataclasses import dataclass, asdict
import re

COLORS = ("burgundy","crimson","maroon","navy","emerald","blue","purple","red","green","black","white","silver","gold","brown","gray","grey","cyan","dark")
WEAPONS = ("sword","katana","blade","axe","spear","bow","staff","hammer","shield","dagger","knife","gun","rifle","umbrella")

# Owner prompts are usually Vietnamese. Map common VI terms to the same canonical
# English tokens the rest of this module (and build_locked_prompt) branches on,
# so structured hard-locks (gender/weapon/color/hair) still fire instead of
# silently falling back to the unstructured raw_prompt tail.
VI_GENDER = {"nữ":"female","gái":"female","con gái":"female","phụ nữ":"female",
             "nam":"male","trai":"male","con trai":"male","đàn ông":"male"}
VI_WEAPONS = {"kiếm":"sword","gươm":"sword","trường kiếm":"sword","katana":"katana","đao":"katana",
              "cung":"bow","cung tên":"bow","rìu":"axe","búa rìu":"axe","thương":"spear","giáo":"spear",
              "gậy":"staff","trượng":"staff","quyền trượng":"staff","búa":"hammer","khiên":"shield",
              "mộc":"shield","dao găm":"dagger","dao":"knife","súng":"gun","súng trường":"rifle",
              "ô":"umbrella","cái ô":"umbrella","dù":"umbrella","umbrella":"umbrella","parasol":"umbrella"}
VI_COLOR_WORDS = {"đỏ":"red","xanh dương":"blue","xanh biển":"blue","xanh navy":"blue","xanh lá":"green",
                  "xanh lục":"green","đen":"black","trắng":"white","bạc":"silver","vàng":"gold",
                  "nâu":"brown","xám":"gray","tím":"purple"}
VI_NOUNS = {"armor":["armor","armour","áo giáp","giáp"],"sash":["sash","belt","cloth","đai","thắt lưng","khăn"],
            "cape":["cape","cloak","áo choàng","khoác"],"hair":["hair","tóc"]}

@dataclass(slots=True)
class CharacterSpec:
    raw_prompt: str
    gender: str | None = None
    weapon_type: str | None = None
    weapon_count: int | None = None
    no_weapon: bool = False  # True when user explicitly says "tay không"/"no weapon"/"empty hands"
    armor_primary: str | None = None
    accent_color: str | None = None
    cape_color: str | None = None
    hair_color: str | None = None
    hair_length: str | None = None
    full_body: bool = True
    single_character: bool = True
    plain_background: bool = True
    render_preset: str = "compact_game"
    # Populated by visual_intent.VisualIntentInterpreter, never by this
    # deterministic parser - kept here (not a separate object) so
    # build_locked_prompt/validate_candidate see one CharacterSpec, matching
    # how gender/weapon/color already flow through this same dataclass.
    face_beauty: list[str] | None = None
    body_style: list[str] | None = None
    hair_style: list[str] | None = None
    costume_style: list[str] | None = None
    pose_style: list[str] | None = None
    camera_style: list[str] | None = None
    lighting_style: list[str] | None = None
    render_style: list[str] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _first_color_near(text: str, nouns: list[str]) -> str | None:
    low=text.lower()
    aliases = {"grey":"gray", "burgundy":"red", "crimson":"red", "maroon":"red", "navy":"blue", "emerald":"green"}
    # English colors keep their original fixed-order priority (existing behavior/tests
    # depend on it, e.g. "dark red" resolving to "red" since it precedes "dark" in COLORS).
    # Vietnamese words are only tried as a fallback so they never reorder English matches.
    for c in COLORS:
        for noun in nouns:
            if re.search(rf"\b{re.escape(c)}\b[^,;]{{0,20}}\b{re.escape(noun)}\b", low) or re.search(rf"\b{re.escape(noun)}\b[^,;]{{0,20}}\b{re.escape(c)}\b", low):
                return aliases.get(c, c)
    for c, canon in VI_COLOR_WORDS.items():
        for noun in nouns:
            if re.search(rf"\b{re.escape(c)}\b[^,;]{{0,20}}\b{re.escape(noun)}\b", low) or re.search(rf"\b{re.escape(noun)}\b[^,;]{{0,20}}\b{re.escape(c)}\b", low):
                return canon
    return None


def parse_character_spec(prompt: str) -> CharacterSpec:
    raw=" ".join((prompt or "").split())
    low=raw.lower()
    gender=None
    if re.search(r"\b(male|man|boy)\b", low): gender="male"
    elif re.search(r"\b(female|woman|girl)\b", low): gender="female"
    if gender is None:
        for term in sorted(VI_GENDER, key=len, reverse=True):
            if re.search(rf"\b{re.escape(term)}\b", low): gender=VI_GENDER[term]; break

    weapon_type=next((w for w in WEAPONS if re.search(rf"\b{w}\b", low)), None)
    if weapon_type is None:
        for term in sorted(VI_WEAPONS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(term)}\b", low): weapon_type=VI_WEAPONS[term]; break
    # Detect "no weapon" / "tay không" / "empty hands" — must come AFTER weapon
    # detection so "không có vũ khí" doesn't match "kiếm" inside the same phrase.
    no_weapon = bool(re.search(r"\b(tay\s*kh[oô]ng|kh[oô]ng\s*(c[oó]\s*)?v[uũ]\s*kh[ií]|empty\s*hands?|no\s*weapon|unarmed|kh[oô]ng\s*(c[oó]\s*)?kiếm)\b", low))
    if no_weapon:
        weapon_type = None  # override: if user says "no weapon", don't keep a weapon
    count=None
    if weapon_type:
        if re.search(rf"\b(one|single|1|một)\b[^,;]{{0,30}}\b{weapon_type}s?\b", low): count=1
        elif re.search(rf"\b(two|dual|2|hai)\b[^,;]{{0,30}}\b{weapon_type}s?\b", low): count=2

    armor=_first_color_near(low, VI_NOUNS["armor"])
    accent=_first_color_near(low, VI_NOUNS["sash"])
    # Recolor phrasing often gives two armor colors, e.g. "burgundy red and gold".
    # Treat the second color as the armor accent when no sash/belt color was supplied.
    if accent is None and armor:
        if re.search(r"\b(?:burgundy|crimson|maroon|red)\b[^,;]{0,18}\band\s+gold\b", low):
            accent = "gold"
        elif re.search(r"\bblue\b[^,;]{0,18}\band\s+(?:gold|purple)\b", low):
            accent = "gold" if "gold" in low else "purple"
    cape_color=_first_color_near(low, VI_NOUNS["cape"])
    hair_color=_first_color_near(low, VI_NOUNS["hair"])
    hair_length="long" if re.search(r"\b(long|dài)\b[^,;]{0,15}\b(hair|tóc)\b|\b(hair|tóc)\b[^,;]{0,15}\b(long|dài)\b", low) else None
    if re.search(r"\b(short|ngắn)\b[^,;]{0,15}\b(hair|tóc)\b|\b(hair|tóc)\b[^,;]{0,15}\b(short|ngắn)\b", low): hair_length="short"

    return CharacterSpec(raw_prompt=raw, gender=gender, weapon_type=weapon_type, weapon_count=count,
                         no_weapon=no_weapon,
                         armor_primary=armor, accent_color=accent, cape_color=cape_color, hair_color=hair_color, hair_length=hair_length)
