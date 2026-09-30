from __future__ import annotations
from .spec_parser import CharacterSpec

BASE_NEGATIVE=(
    "text, logo, watermark, signature, UI, menu, border, frame, "
    "multiple people, duplicate person, extra body, extra limbs, cropped head, cropped feet, "
    "portrait, close-up, upper body only, detailed scenery, room, city, deformed anatomy, blurry face"
)

# Framing/composition phrases are compatible with any body style (chibi or
# elegant) - always applied for compact_game. Proportion phrases specifically
# assume chibi ratios and are skipped when visual_intent.py's beauty_priority
# asked for elegant/long-legged proportions instead (section 23: a prompt
# must never say both "short legs" and "long elegant legs").
COMPACT_FRAMING=(
    "CHARACTER TWO THIRDS CANVAS HEIGHT", "EMPTY MARGIN AROUND CHARACTER",
    "NO PEDESTAL, FEET ON PLAIN BACKGROUND",
)
COMPACT_PROPORTIONS=(
    "COMPACT CHIBI PROPORTIONS", "LARGE HEAD, SHORT BODY",
)
COMPACT_NEGATIVE_FRAMING=(
    "character filling entire frame, close crop, pedestal, display base, statue stand"
)
COMPACT_NEGATIVE_PROPORTIONS=(
    "tall elongated realistic proportions, fashion model, long legs, giant body"
)

# ─── Object prompt mapping ───────────────────────────────────────────
# Each entry: (positive_clause, negative_clause)
# Positive goes into the hard list at HIGH priority (right after gender,
# before style/repair).  Negative blocks objects that are easily confused.
# This is the single source of truth for how a requested object becomes
# prompt text — no other file invents object descriptions.
OBJECT_PROMPTS: dict[str, tuple[str, str]] = {
    "sword": (
        "ONE CLEARLY VISIBLE LONG SWORD WITH BLADE, GUARD AND HANDLE, HELD NATURALLY IN ONE HAND",
        "umbrella, parasol, gun, rifle, firearm, spear, bow, second sword, dual wielding, dagger, scabbard, sheath",
    ),
    "katana": (
        "ONE CLEARLY VISIBLE KATANA WITH CURVED BLADE AND WRAPPED HANDLE, HELD IN ONE HAND",
        "umbrella, parasol, gun, rifle, firearm, spear, bow, second sword, dual wielding, dagger, scabbard, sheath",
    ),
    "blade": (
        "ONE CLEARLY VISIBLE BLADED WEAPON WITH METAL BLADE AND HANDLE, HELD IN ONE HAND",
        "umbrella, parasol, gun, rifle, firearm, spear, bow, second blade, dual wielding, dagger, scabbard, sheath",
    ),
    "bow": (
        "ONE CLEARLY VISIBLE BOW WITH CURVED LIMBS AND BOWSTRING, HELD IN ONE HAND, NO SWORD, NO GUN",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, dagger, second bow, duplicate bow",
    ),
    "spear": (
        "ONE CLEARLY VISIBLE SPEAR WITH LONG SHAFT AND SPEARHEAD, HELD IN TWO HANDS",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, second spear, dagger",
    ),
    "axe": (
        "ONE CLEARLY VISIBLE AXE WITH METAL HEAD AND WOODEN HANDLE, HELD IN ONE HAND",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, second axe, dagger",
    ),
    "staff": (
        "ONE CLEARLY VISIBLE LONG STAFF OR WAND, WOODEN POLE HELD IN ONE OR TWO HANDS",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, spear, dagger",
    ),
    "hammer": (
        "ONE CLEARLY VISIBLE HAMMER WITH METAL HEAD AND HANDLE, HELD IN ONE OR TWO HANDS",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, spear, dagger",
    ),
    "shield": (
        "ONE CLEARLY VISIBLE SHIELD ON ONE ARM, ROUND OR KITE-SHAPED, NO OTHER WEAPON",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, spear, dagger, staff",
    ),
    "dagger": (
        "ONE CLEARLY VISIBLE SHORT DAGGER, SMALL BLADE, HELD IN ONE HAND",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, spear, staff, second dagger",
    ),
    "knife": (
        "ONE CLEARLY VISIBLE KNIFE, SHORT BLADE, HELD IN ONE HAND",
        "sword, katana, blade, umbrella, parasol, gun, rifle, firearm, bow, spear, staff, second knife",
    ),
    "gun": (
        "ONE CLEARLY VISIBLE GUN OR PISTOL, HELD IN ONE HAND",
        "sword, katana, blade, umbrella, parasol, bow, spear, staff, dagger, second gun, rifle",
    ),
    "rifle": (
        "ONE CLEARLY VISIBLE RIFLE, LONG BARREL, HELD IN TWO HANDS",
        "sword, katana, blade, umbrella, parasol, bow, spear, staff, dagger, pistol, second rifle",
    ),
    "umbrella": (
        "A CLEARLY VISIBLE HANDHELD UMBRELLA OR PARASOL, OPEN CANOPY, HANDLE HELD IN ONE HAND",
        "sword, katana, blade, gun, rifle, firearm, spear, bow, staff, dagger, axe, shield, second umbrella",
    ),
}


def build_locked_prompt(spec: CharacterSpec, repair_directives: list[str] | None=None) -> tuple[str,str]:
    # Priority-ordered hard constraints.  The most identity-critical clauses
    # (single character, full body, background) go FIRST so they survive even
    # if the CLIP token limit trims the tail.  Style/generic polish words go last.
    hard=["ONE SINGLE CHARACTER ONLY", "FULL BODY HEAD TO BOOTS", "BOTH FEET VISIBLE", "CENTERED IDLE POSE", "PLAIN LIGHT GRAY BACKGROUND"]
    neg=[BASE_NEGATIVE]
    wants_elegant_body = bool(getattr(spec, "body_style", None))
    if getattr(spec,"render_preset","compact_game")=="compact_game":
        hard.extend(COMPACT_FRAMING)
        neg.append(COMPACT_NEGATIVE_FRAMING)
        if not wants_elegant_body:
            hard.extend(COMPACT_PROPORTIONS)
            neg.append(COMPACT_NEGATIVE_PROPORTIONS)
    if spec.gender:
        hard.append(f"ADULT {spec.gender.upper()} CHARACTER")
        neg.append("female character, feminine face" if spec.gender=="male" else "male character, masculine face")
    if getattr(spec, "body_style", None): hard.extend(spec.body_style)
    if getattr(spec, "face_beauty", None): hard.extend(spec.face_beauty)
    if spec.armor_primary:
        hard.append(f"PRIMARY ARMOR COLOR {spec.armor_primary.upper()}")
        neg.append("white basic clothes, sportswear, plain bodysuit")
    if spec.accent_color:
        hard.append(f"{spec.accent_color.upper()} SASH ACCENT")
    if getattr(spec, "cape_color", None):
        hard.append(f"CAPE COLOR {spec.cape_color.upper()}")
    if spec.hair_color:
        hard.append(f"{spec.hair_color.upper()} HAIR")
    if spec.hair_length:
        hard.append(f"{spec.hair_length.upper()} HAIR")
    if getattr(spec, "hair_style", None): hard.extend(spec.hair_style)
    if getattr(spec, "costume_style", None): hard.extend(spec.costume_style)
    # ─── Object / weapon clause ───
    # Uses OBJECT_PROMPTS dict above — single source of truth for how each
    # requested object becomes prompt text.  Goes at HIGH priority (before
    # style/repair/generic) so the CLIP token fitting never trims it.
    if spec.weapon_type and spec.weapon_type in OBJECT_PROMPTS:
        pos_clause, neg_clause = OBJECT_PROMPTS[spec.weapon_type]
        hard.append(pos_clause)
        neg.append(neg_clause)
    elif spec.no_weapon:
        hard.append("EMPTY HANDS, NO WEAPON, NO SWORD, NO UMBRELLA, NO BOW, NO GUN")
        neg.append("sword, katana, blade, umbrella, parasol, bow, spear, staff, dagger, axe, shield, gun, rifle, firearm")
    elif spec.weapon_type:
        # Fallback for any weapon_type not in OBJECT_PROMPTS (future-proof)
        hard.append(f"ONE VISIBLE {spec.weapon_type.upper()}")
        neg.append("second weapon, dual wielding, gun, rifle, firearm")
    if getattr(spec, "pose_style", None): hard.extend(spec.pose_style)
    if getattr(spec, "camera_style", None): hard.extend(spec.camera_style)
    if getattr(spec, "lighting_style", None): hard.extend(spec.lighting_style)
    if getattr(spec, "render_style", None): hard.extend(spec.render_style)
    has_beauty_intent = any(getattr(spec, k, None) for k in
        ("face_beauty", "body_style", "hair_style", "costume_style", "pose_style", "camera_style", "lighting_style", "render_style"))
    if has_beauty_intent:
        from .visual_intent import BEAUTY_NEGATIVE
        neg.append(BEAUTY_NEGATIVE)
    if repair_directives:
        hard.extend(d.upper() for d in repair_directives if d)
    hard.append("NO REDESIGN, CLEAN 2D GAME ASSET")
    # Do NOT append the full raw_prompt verbatim - it duplicates keywords
    # already extracted above (gender, weapon, colors) and wastes CLIP's
    # 77-token budget, causing truncation of critical tail clauses.
    positive=". ".join(hard)
    return positive, ", ".join(neg)
