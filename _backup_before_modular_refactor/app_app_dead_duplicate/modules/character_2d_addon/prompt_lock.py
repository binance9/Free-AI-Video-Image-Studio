from __future__ import annotations
from .spec_parser import CharacterSpec

BASE_NEGATIVE=(
    "text, letters, words, logo, watermark, signature, UI, menu, panel, browser, screenshot, border, frame, "
    "multiple people, duplicate person, extra body, extra arms, extra legs, duplicate limbs, cropped head, cropped feet, "
    "portrait, close-up, upper body only, detailed scenery, room, city, landscape, deformed anatomy, blurry face"
)

COMPACT_POSITIVE=(
    "COMPACT CHIBI-INSPIRED GAME CHARACTER PROPORTIONS", "SHORT COMPACT BODY", "SLIGHTLY OVERSIZED HEAD", 
    "SHORTER LIMBS", "READABLE CLEAN SILHOUETTE", "CHARACTER OCCUPIES ABOUT TWO THIRDS OF THE CANVAS HEIGHT",
    "GENEROUS EMPTY MARGIN AROUND THE ENTIRE CHARACTER", "ZOOMED OUT SPRITE-FRIENDLY COMPOSITION",
    "HEAD TO BODY RATIO ABOUT ONE TO FOUR, SHORT TORSO, SHORT LEGS, COMPACT ARMS",
    "NO PEDESTAL, NO DISPLAY BASE, FEET STAND DIRECTLY ON PLAIN BACKGROUND"
)
COMPACT_NEGATIVE=(
    "tall elongated realistic proportions, fashion model proportions, long legs, giant heroic body, "
    "character filling entire frame, close crop, oversized character, cinematic portrait, splash art composition, "
    "pedestal, display base, platform, statue stand, glowing floating particles, cape made of light"
)


def build_locked_prompt(spec: CharacterSpec, repair_directives: list[str] | None=None) -> tuple[str,str]:
    hard=["ONE SINGLE CHARACTER ONLY", "FULL BODY HEAD TO BOOTS", "BOTH FEET FULLY VISIBLE", "CENTERED NEUTRAL IDLE POSE", "PLAIN UNIFORM LIGHT GRAY BACKGROUND"]
    neg=[BASE_NEGATIVE]
    if getattr(spec,"render_preset","compact_game")=="compact_game":
        hard.extend(COMPACT_POSITIVE)
        neg.append(COMPACT_NEGATIVE)
    if spec.gender:
        hard.append(f"ADULT {spec.gender.upper()} CHARACTER")
        neg.append("female character, feminine face" if spec.gender=="male" else "male character, masculine face")
    if spec.armor_primary:
        hard.append(f"PRIMARY ARMOR COLOR MUST VISIBLY BE {spec.armor_primary.upper()}, MOST ARMOR PLATES ARE {spec.armor_primary.upper()}")
        neg.append("white basic clothes, sportswear, plain bodysuit, casual shirt")
    if spec.accent_color:
        hard.append(f"ONE CLEAR {spec.accent_color.upper()} WAIST SASH OR CLOTH ACCENT IS MANDATORY")
    if getattr(spec, "cape_color", None):
        hard.append(f"CAPE OR CLOAK COLOR MUST VISIBLY BE {spec.cape_color.upper()}")
    if spec.hair_color:
        hard.append(f"{spec.hair_color.upper()} HAIR")
    if spec.hair_length:
        hard.append(f"{spec.hair_length.upper()} HAIR")
    if spec.weapon_type:
        if spec.weapon_count == 1:
            if spec.weapon_type in {"sword", "katana", "blade"}:
                hard.append(f"EXACTLY ONE VISIBLE {spec.weapon_type.upper()} TOTAL, ONE BLADED SWORD ONLY, HELD IN RIGHT HAND, LEFT HAND EMPTY, NO FIREARM SHAPE, NO GUN-LIKE OBJECT")
                neg.append("second weapon, extra weapon, dual wielding, two swords, dagger, knife, scabbard, sheath, mace, gun, rifle, pistol, firearm, camera, launcher, cannon")
            elif spec.weapon_type == "bow":
                hard.append("EXACTLY ONE VISIBLE BOW TOTAL, HELD NATURALLY IN ONE HAND, ONE QUIVER IS ALLOWED, NO SWORD, NO GUN")
                neg.append("sword, katana, blade, dagger, knife, gun, rifle, pistol, firearm, camera, launcher, cannon, second bow, duplicate bow")
            else:
                hard.append(f"EXACTLY ONE VISIBLE {spec.weapon_type.upper()} TOTAL, NO SECOND WEAPON")
                neg.append("second weapon, extra weapon, dual wielding, gun, rifle, pistol, firearm, camera, launcher, cannon")
        else:
            hard.append(f"VISIBLE {spec.weapon_type.upper()}")
    if repair_directives:
        hard.extend(d.upper() for d in repair_directives if d)
    hard.append("NO REDESIGN, NO INVENTED EQUIPMENT, CLEAN 2D GAME ASSET, SIMPLE READABLE DETAILS")
    positive=". ".join(hard+[spec.raw_prompt])
    return positive, ", ".join(neg)
