from __future__ import annotations

def plan_repairs(issues: list[str], spec) -> list[str]:
    out=[]
    mapping={
        "face":"CLEAR SHARP FACE, OPEN EYES, DEFINED NOSE, NATURAL MOUTH",
        "fullbody":"ZOOM OUT, ENTIRE BODY VISIBLE, HEAD AND BOTH BOOTS INSIDE FRAME",
        "background":"REMOVE ALL SCENERY AND UI, FLAT LIGHT GRAY BACKGROUND",
        "multiple_characters":"REMOVE ALL OTHER PEOPLE, ONE PERSON ONLY",
        "gender":f"STRICT {str(spec.gender).upper()} IDENTITY, DO NOT CHANGE GENDER" if getattr(spec,"gender",None) else "",
        "weapon_type":f"SHOW A CLEAR {str(spec.weapon_type).upper()}" if getattr(spec,"weapon_type",None) else "",
        "weapon_count":f"EXACTLY ONE {str(spec.weapon_type).upper()} ONLY, LEFT HAND EMPTY, NO SECOND WEAPON" if getattr(spec,"weapon_type",None) else "",
        "armor_color":f"ARMOR MUST BE CLEARLY {str(spec.armor_primary).upper()}, NOT WHITE OR SILVER" if getattr(spec,"armor_primary",None) else "",
        "accent_color":f"ADD A CLEARLY VISIBLE {str(spec.accent_color).upper()} SASH" if getattr(spec,"accent_color",None) else "",
        "cape_color":f"CAPE OR CLOAK MUST BE CLEARLY {str(spec.cape_color).upper()}" if getattr(spec,"cape_color",None) else "",
        "plain_background":"REMOVE SCENERY, PLAIN LIGHT GRAY BACKGROUND",
        "single_character":"ONE SINGLE PERSON ONLY",
        "compact_composition":"ZOOM OUT MORE, HEAD TO BODY ABOUT 1:4, SHORT COMPACT BODY, SHORT TORSO AND LEGS, CHARACTER ABOUT TWO THIRDS OF CANVAS HEIGHT, LARGE EMPTY MARGINS",
        "compact_proportions":"REDRAW AS COMPACT CHIBI GAME PROPORTIONS, LARGE HEAD, SHORT TORSO, SHORT LEGS, DO NOT USE REALISTIC ADULT PROPORTIONS",
        "no_pedestal":"REMOVE PEDESTAL, DISPLAY BASE AND PLATFORM; FEET STAND DIRECTLY ON PLAIN BACKGROUND",
        "too_little_visible_content":"MAKE THE CHARACTER CLEARLY VISIBLE AND LARGER INSIDE THE FRAME, NO EMPTY CANVAS",
        "too_dark":"USE BRIGHT STUDIO LIGHTING, NO UNDEREXPOSED DARK RENDER",
        "too_flat":"ADD CLEAR SHADING AND READABLE CHARACTER DETAIL, NOT A FLAT BLANK IMAGE",
        "mostly_black":"DO NOT OUTPUT A BLACK IMAGE; USE A LIGHT GRAY BACKGROUND AND CLEAR CHARACTER COLORS",
        "too_few_colors":"INCREASE VISUAL DETAIL AND SEPARATE CHARACTER FROM THE BACKGROUND",
        "fully_transparent":"RENDER A FULLY VISIBLE OPAQUE CHARACTER, NOT A TRANSPARENT OR EMPTY IMAGE",
        "dark_background_edges":"USE A BRIGHT UNIFORM LIGHT GRAY BACKGROUND ACROSS ALL FOUR EDGES AND CORNERS, NO BLACK BORDER OR DARK VIGNETTE",
    }
    for issue in issues:
        d=mapping.get(issue,"")
        if d and d not in out: out.append(d)
    return out[:8]
