from __future__ import annotations
from pathlib import Path

from .output_guard import save_export_image

# Relaxed: removed compact_proportions and no_pedestal from CRITICAL_UNCERTAIN.
# These CLIP-based checks are too unreliable (low confidence on good images) to
# be automatic export blockers.  weapon_type stays critical (if user asks for
# sword, image must show sword).  Gender stays critical for identity.
CRITICAL_UNCERTAIN={"gender","weapon_type","weapon_count","armor_color"}

def decide_export(base_gate: dict, attribute_gate: dict, min_score: int) -> dict:
    blockers=[]
    if not base_gate.get("passed"):
        blockers.extend(base_gate.get("issues",[]))
    blockers.extend(attribute_gate.get("hard_failures",[]))
    uncertain=list(attribute_gate.get("uncertain",[]))
    blockers.extend([x for x in uncertain if x in CRITICAL_UNCERTAIN])
    blockers=list(dict.fromkeys(blockers))
    accepted=bool(base_gate.get("quality_score",0)>=min_score and not blockers)
    return {"accepted":accepted,"blockers":blockers,"uncertain":uncertain,"quality_score":base_gate.get("quality_score",0),"minimum_score":min_score,"strict_attribute_gate":True}

def export_if_passed(candidate: str|Path, final_path: str|Path, gate: dict, *, flatten: bool = True) -> str|None:
    if not gate.get("accepted"): return None
    return save_export_image(candidate, final_path, flatten=flatten)
