from __future__ import annotations
from pathlib import Path
from .quality_gate import evaluate_anchor
from .export_gate import decide_export
from .compact_composition import inspect_compact_composition

def validate_candidate(image_path: str|Path, spec, attribute_lock, min_score: int) -> dict:
    base=evaluate_anchor(image_path,min_score=min_score)
    attrs=attribute_lock.inspect(image_path,spec)
    compact=None
    if getattr(spec,"render_preset","compact_game")=="compact_game":
        compact=inspect_compact_composition(image_path)
        if not compact.get("ok"):
            attrs=dict(attrs)
            attrs["hard_failures"]=list(dict.fromkeys(list(attrs.get("hard_failures",[]))+["compact_composition"]))
    gate=decide_export(base,attrs,min_score)
    return {"base":base,"attributes":attrs,"compact_composition":compact,"gate":gate}
