"""Prompt builder and prompt guard for do_vat_3d.

Muc tieu:
- do_vat_3d chi tao DO VAT, khong duoc nhoi prompt nhan vat.
- prompt gui sang tao_anh_ai phai NGAN, RO, object-only de tranh CLIP truncation.
- cac category object thong thuong se chan tu khoa human/character de tranh AI ve nguoi.
"""
from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")

_CATEGORY_HINTS = {
    "cay": "tree object, game prop",
    "da": "rock object, game prop",
    "co_bui": "grass or bush object, game prop",
    "ruong": "treasure chest object, game prop",
    "thung": "barrel or crate object, game prop",
    "hang_rao": "fence segment object, game prop",
    "cot": "pillar object, game prop",
    "den": "lamp object, game prop",
    "nha_nho": "small house object, game prop",
    "cong": "gate object, game prop",
    "tuong": "statue object, game prop",
    "trang_tri": "decoration object, game prop",
    "tu_do": "3d game prop object",
}

_STRICT_OBJECT_CATEGORIES = {
    "cay", "da", "co_bui", "ruong", "thung", "hang_rao", "cot",
    "den", "nha_nho", "cong", "trang_tri",
}

_BLOCKED_HUMAN_TERMS = {
    "character", "human", "person", "people", "man", "woman", "boy", "girl",
    "warrior", "archer", "hero", "npc", "face", "head", "hair", "eye", "eyes",
    "hand", "hands", "arm", "arms", "leg", "legs", "body", "anatomy", "costume",
    "portrait", "full body", "nhân vật", "nguoi", "người", "con người", "mặt",
    "khuôn mặt", "tay", "chân", "cánh tay", "cơ thể", "toàn thân", "cung thủ",
    "chiến binh", "anh hùng",
}


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", (text or "").strip())


def kiem_tra_prompt_do_vat(prompt: str, category: str) -> str:
    clean = _clean(prompt)
    if len(clean) < 3:
        raise ValueError("Mô tả đồ vật quá ngắn")
    cat = (category or "").strip().lower()
    if cat in _STRICT_OBJECT_CATEGORIES:
        lower = clean.lower()
        hits = [term for term in sorted(_BLOCKED_HUMAN_TERMS) if term in lower]
        if hits:
            short_hits = ", ".join(hits[:6])
            raise ValueError(
                "Prompt đồ vật đang chứa từ khóa nhân vật/người "
                f"({short_hits}). Module do_vat_3d chỉ nhận đồ vật; "
                "hãy mô tả vật thể/cảnh quan/prop thay vì con người."
            )
    return clean


def tao_prompt_concept_do_vat(prompt: str, category: str) -> str:
    clean = kiem_tra_prompt_do_vat(prompt, category)
    cat = (category or "tu_do").strip().lower()
    hint = _CATEGORY_HINTS.get(cat, _CATEGORY_HINTS["tu_do"])
    return _clean(
        f"{hint}, {clean}, single isolated object, centered, full object visible, plain background, "
        "no human, no character, no face, no body, no arms, no legs, no text"
    )
