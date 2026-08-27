from __future__ import annotations

from dataclasses import dataclass, asdict
import re


_COLOR_ALIASES = {
    "black": ("black", "đen", "den"),
    "white": ("white", "trắng", "trang"),
    "silver": ("silver", "bạc", "bac"),
    "gray": ("gray", "grey", "xám", "xam"),
    "red": ("red", "đỏ", "do"),
    "blue": ("blue", "xanh dương", "xanh duong", "lam"),
    "cyan": ("cyan", "aqua", "xanh ngọc", "xanh ngoc"),
    "green": ("green", "xanh lá", "xanh la"),
    "purple": ("purple", "violet", "tím", "tim"),
    "gold": ("gold", "golden", "vàng", "vang"),
    "brown": ("brown", "nâu", "nau"),
}

_WEAPON_ALIASES = {
    "sword": ("sword", "swords", "kiếm", "kiem"),
    "katana": ("katana", "samurai sword"),
    "blade": ("blade", "blades", "đao", "dao"),
    "spear": ("spear", "thương", "thuong"),
    "bow": ("bow", "cung"),
    "staff": ("staff", "rod", "gậy", "gay"),
    "axe": ("axe", "axes", "rìu", "riu"),
}


@dataclass(slots=True)
class CommandSpec:
    raw_prompt: str
    gender: str | None = None
    hair_color: str | None = None
    hair_length: str | None = None
    armor_color: str | None = None
    cloth_colors: tuple[str, ...] = ()
    weapon_type: str | None = None
    weapon_count: int | None = None
    pose: str | None = None
    view: str | None = None
    background_color: str | None = None
    style: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def dual_weapon(self) -> bool:
        return self.weapon_count == 2


def _norm(text: str) -> str:
    raw = (text or "").strip().lower()
    raw = re.sub(r"[,.;:/|()\[\]{}]+", " ", raw)
    return " " + re.sub(r"\s+", " ", raw) + " "


def _contains(text: str, aliases: tuple[str, ...]) -> bool:
    return any((" " + re.sub(r"\s+", " ", a.lower()).strip() + " ") in text for a in aliases)


def _first_color(text: str, *, near: tuple[str, ...] | None = None) -> str | None:
    if near:
        # Prefer a directly adjacent color ("silver armor", "black hair").
        for gap in (0, 1):
            for obj in near:
                obj_re = re.escape(obj.lower())
                for color, aliases in _COLOR_ALIASES.items():
                    for alias in aliases:
                        color_re = re.escape(alias.lower())
                        middle = rf"(?:\s+\w+){{{gap}}}\s+" if gap else r"\s+"
                        before = rf"(?<!\w){color_re}(?!\w){middle}(?<!\w){obj_re}(?!\w)"
                        after = rf"(?<!\w){obj_re}(?!\w){middle}(?<!\w){color_re}(?!\w)"
                        if re.search(before, text) or re.search(after, text):
                            return color
        return None
    for color, aliases in _COLOR_ALIASES.items():
        if _contains(text, aliases):
            return color
    return None


def _all_colors(text: str) -> list[str]:
    out = []
    for color, aliases in _COLOR_ALIASES.items():
        if _contains(text, aliases):
            out.append(color)
    return out


def parse_command_spec(prompt: str) -> CommandSpec:
    text = _norm(prompt)

    gender = None
    if any(k in text for k in (" male ", " man ", " nam ", " đàn ông ", " dan ong ")):
        gender = "male"
    if any(k in text for k in (" female ", " woman ", " nữ ", " nu ", " cô gái ", " co gai ")):
        gender = "female"

    hair_color = _first_color(text, near=("hair", "tóc", "toc"))
    hair_length = None
    if (re.search(r"\blong\b(?:\s+\w+){0,3}\s+hair\b", text)
            or " tóc dài " in text or " toc dai " in text
            or re.search(r"\btóc\b(?:\s+\w+){0,3}\s+dài\b", text)):
        hair_length = "long"
    elif (re.search(r"\bshort\b(?:\s+\w+){0,3}\s+hair\b", text)
            or " tóc ngắn " in text or " toc ngan " in text):
        hair_length = "short"

    armor_color = _first_color(text, near=("armor", "armour", "giáp", "giap"))
    colors = _all_colors(text)
    cloth_colors = tuple(c for c in colors if c not in {armor_color, hair_color, "gray"})

    weapon_type = None
    for kind, aliases in _WEAPON_ALIASES.items():
        if _contains(text, aliases):
            weapon_type = kind
            break

    weapon_count = None
    dual_terms = (
        " dual ", " two ", " 2 ", " pair ", " both hands ", " one in each hand ",
        " hai ", " đôi ", " doi ", " song kiếm ", " song kiem ", " song đao ", " song dao ",
    )
    single_terms = (" single ", " one sword ", " one blade ", " một kiếm ", " mot kiem ", " một đao ", " mot dao ")
    if weapon_type and any(k in text for k in dual_terms):
        weapon_count = 2
    elif weapon_type and any(k in text for k in single_terms):
        weapon_count = 1

    pose = None
    if any(k in text for k in (" idle ", " đứng yên ", " dung yen ", " neutral stance ")):
        pose = "idle"
    elif any(k in text for k in (" run ", " running ", " chạy ", " chay ")):
        pose = "run"
    elif any(k in text for k in (" attack ", " attacking ", " chém ", " chem ", " đánh ", " danh ")):
        pose = "attack"

    view = None
    if any(k in text for k in (" front ", " front-facing ", " chính diện ", " chinh dien ")):
        view = "front"
    elif any(k in text for k in (" back view ", " from back ", " sau lưng ", " sau lung ")):
        view = "back"
    elif any(k in text for k in (" left view ", " facing left ", " hướng trái ", " huong trai ")):
        view = "left"
    elif any(k in text for k in (" right view ", " facing right ", " hướng phải ", " huong phai ")):
        view = "right"

    background_color = None
    # Background color must be explicit; do not steal a nearby armor/clothing color.
    for color, aliases in _COLOR_ALIASES.items():
        found = False
        for alias in aliases:
            a = re.escape(alias.lower())
            if re.search(rf"\b{a}\s+(?:plain\s+)?background\b", text) or re.search(rf"\bbackground\s+(?:color\s+)?{a}\b", text):
                background_color = color
                found = True
                break
        if found:
            break
    if " nền xám " in text or " nen xam " in text:
        background_color = "gray"

    style = None
    if " anime " in text:
        style = "anime"
    elif any(k in text for k in (" semi-realistic ", " semi realistic ", " bán thực ", " ban thuc ")):
        style = "semi-realistic"
    elif any(k in text for k in (" 2d ", " illustration ", " concept art ")):
        style = "2D game illustration"

    return CommandSpec(
        raw_prompt=(prompt or "").strip(),
        gender=gender,
        hair_color=hair_color,
        hair_length=hair_length,
        armor_color=armor_color,
        cloth_colors=cloth_colors,
        weapon_type=weapon_type,
        weapon_count=weapon_count,
        pose=pose,
        view=view,
        background_color=background_color,
        style=style,
    )
