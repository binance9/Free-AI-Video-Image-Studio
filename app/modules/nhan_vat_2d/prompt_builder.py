from __future__ import annotations

import re

from .character_profile import CharacterProfile
from .direction_builder import build_pose_hint

# Keep exclusions compact so the positive prompt keeps most of CLIP's short context.
NEGATIVE_PROMPT = (
    "text, letters, words, numbers, typography, logo, watermark, signature, user interface, UI, menu, panel, window, browser, screenshot, border, frame, "
    "multiple characters, two people, group, crowd, duplicate person, extra head, extra body, duplicate limbs, "
    "detailed background, scenery, landscape, room, city, poster, character sheet layout, "
    "portrait, close-up, bust shot, upper body only, cropped head, cropped legs, cropped feet, off frame, "
    "faceless, blurry face, deformed face, bad anatomy, malformed hands, extra fingers, "
    "oversized weapon, weapon covering face, extra weapon, second sword, two swords, dual wielding, dagger, knife, scabbard, sheath, invented equipment, generic sportswear, plain bodysuit, basic casual clothes, "
    "figurine, statue, toy figure, action figure, PVC figure, display stand, pedestal, round base, product photography, diorama"
)

_ANCHOR_CORE = (
    "full body 2D game sprite sheet character, ONE SINGLE CHARACTER ONLY, entire body visible, both feet visible, "
    "visible eyes, plain clean background"
)

# Attribute words are intentionally small and concrete. The phrases containing
# these words are copied from the user's literal prompt and moved to the FRONT.
_ATTRIBUTE_NOUNS = (
    "armor", "armour", "sash", "belt", "robe", "coat", "jacket", "shirt", "pants", "trousers",
    "boots", "shoes", "gloves", "cape", "cloak", "helmet", "hat", "hair", "sword", "blade", "katana",
    "bow", "axe", "spear", "staff", "dagger", "shield", "gun", "rifle", "hammer", "weapon"
)


def _literal_user_text(text: str, max_words: int) -> str:
    text = re.sub(r"[\r\n\t]+", " ", text or "")
    text = re.sub(r"[^\w\-\s,./]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    words = text.split()
    return " ".join(words[:max(1, int(max_words))])


def compact_user_prompt(profile: CharacterProfile, max_words: int = 20) -> str:
    source = " ".join(profile.notes or [])
    return _literal_user_text(source, max_words)


def _required_attributes(profile: CharacterProfile, max_items: int = 6) -> list[str]:
    """Extract short literal attribute phrases such as 'blue armor' or
    'one straight sword' without inventing anything not present in the prompt.
    """
    source = compact_user_prompt(profile, 36)
    if not source:
        return []

    chunks = [c.strip() for c in re.split(r"[,;]", source) if c.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        low = chunk.lower()
        if not any(re.search(rf"\b{re.escape(noun)}\b", low) for noun in _ATTRIBUTE_NOUNS):
            continue
        # Keep only a short tail around the matched attribute noun so CLIP sees
        # the concrete design before generic composition instructions.
        words = chunk.split()
        noun_idx = None
        for i, word in enumerate(words):
            clean = re.sub(r"[^\w-]", "", word.lower())
            if clean in _ATTRIBUTE_NOUNS:
                noun_idx = i
                break
        if noun_idx is None:
            continue
        start = max(0, noun_idx - 3)
        end = min(len(words), noun_idx + 2)
        phrase = " ".join(words[start:end]).strip(" ,")
        key = phrase.lower()
        if phrase and key not in seen:
            seen.add(key)
            out.append(phrase)
        if len(out) >= max_items:
            break
    return out


def _mandatory_prefix(profile: CharacterProfile) -> str:
    attrs = _required_attributes(profile)
    if attrs:
        return "MANDATORY DESIGN: " + ", ".join(attrs)
    custom = compact_user_prompt(profile, 16)
    return f"MANDATORY DESIGN: {custom}" if custom else ""



def _identity_lock(profile: CharacterProfile) -> str:
    source = compact_user_prompt(profile, 32).lower()
    if re.search(r"\b(male|man|boy)\b", source):
        return "ADULT MALE CHARACTER, male face, not female"
    if re.search(r"\b(female|woman|girl)\b", source):
        return "ADULT FEMALE CHARACTER, female face, not male"
    return ""


def _weapon_count_lock(profile: CharacterProfile) -> str:
    source = compact_user_prompt(profile, 40).lower()
    one_sword = bool(re.search(r"\b(one|single|1)\b[^,;]{0,24}\b(sword|blade|katana)\b", source))
    if one_sword:
        return "EXACTLY ONE VISIBLE SWORD TOTAL, no second weapon"
    return ""

def build_anchor_prompt(profile: CharacterProfile) -> str:
    mandatory = _mandatory_prefix(profile)
    identity = _identity_lock(profile)
    weapon_lock = _weapon_count_lock(profile)
    pieces = [_ANCHOR_CORE]
    if mandatory:
        pieces.append(mandatory)
    if identity:
        pieces.append(identity)
    if weapon_lock:
        pieces.append(weapon_lock)
    custom = compact_user_prompt(profile, 10)
    if custom:
        pieces.append(custom)
    pieces.append("clear face, exact colors, exact gender, no redesign, no invented gear, no text, no UI")
    return ". ".join(pieces)

def build_repair_prompt(profile: CharacterProfile, issues: list[str]) -> str:
    mandatory = _mandatory_prefix(profile)
    identity = _identity_lock(profile)
    weapon_lock = _weapon_count_lock(profile)
    fixes = []
    if "face" in issues:
        fixes.append("clear open eyes, defined nose, natural mouth")
    if "fullbody" in issues:
        fixes.append("entire body head to boots, both feet visible")
    if "background" in issues:
        fixes.append("plain uniform light gray background, remove scenery, remove text and panels")
    if "multiple_characters" in issues:
        fixes.append("exactly one character, remove duplicates")
    if "dark" in issues:
        fixes.append("balanced lighting, readable clothing")
    fix_text = ", ".join(fixes) or "preserve full body, clear face, plain background"
    return (
        f"{identity}. {weapon_lock}. {mandatory}. SAME CHARACTER, {fix_text}. Preserve gender, every mandatory clothing color and weapon count exactly. "
        "No substitute outfit, no redesign, no extra gear, no text, no UI"
    )


def build_face_refine_prompt(profile: CharacterProfile) -> str:
    mandatory = _mandatory_prefix(profile)
    identity = _identity_lock(profile)
    return (
        f"{identity}. same face, clear open eyes with visible pupils, defined nose, natural lips, clean jawline, preserve identity. {mandatory}. "
        "Do not change gender, hair, clothing colors or equipment"
    )


def build_frame_prompt(profile: CharacterProfile, direction: str, action: str, frame_index: int, total_frames: int) -> str:
    pose = build_pose_hint(direction, action, frame_index, total_frames)
    mandatory = _mandatory_prefix(profile)
    identity = _identity_lock(profile)
    weapon_lock = _weapon_count_lock(profile)
    return (
        f"{identity}. {weapon_lock}. {mandatory}. same fantasy swordsman, ONE character, same exact clothing colors and exact same weapon count, {pose}. "
        "Full body head to boots, centered game sprite, plain uniform background, no redesign, no text, no UI"
    )
