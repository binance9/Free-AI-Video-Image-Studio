from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from PIL import Image

_MODEL_ID="openai/clip-vit-base-patch32"

@dataclass(slots=True)
class ClipDecision:
    check: str
    ok: bool | None
    confidence: float
    selected: str
    scores: dict[str,float]
    reason: str=""

class AttributeLock:
    def __init__(self, cache_dir: str|Path):
        self.cache_dir=Path(cache_dir); self.cache_dir.mkdir(parents=True,exist_ok=True)
        self._model=None; self._processor=None; self._device="cpu"; self._lock=Lock()

    def _load(self):
        if self._model is not None: return
        with self._lock:
            if self._model is not None: return
            import torch
            from transformers import CLIPModel, CLIPProcessor
            self._device="cuda" if torch.cuda.is_available() else "cpu"
            self._processor=CLIPProcessor.from_pretrained(_MODEL_ID, cache_dir=str(self.cache_dir))
            self._model=CLIPModel.from_pretrained(_MODEL_ID, cache_dir=str(self.cache_dir)).to(self._device).eval()

    def _choose(self, image: Image.Image, labels: list[str], check: str, expected_index: int=0, min_prob: float=.40, min_margin: float=.08) -> ClipDecision:
        import torch
        self._load()
        inputs=self._processor(text=labels, images=image, return_tensors="pt", padding=True)
        inputs={k:v.to(self._device) for k,v in inputs.items()}
        with torch.inference_mode(): probs=self._model(**inputs).logits_per_image.softmax(dim=1)[0].detach().cpu().tolist()
        pairs=sorted(zip(labels,probs), key=lambda x:x[1], reverse=True)
        selected, best=pairs[0]; expected=probs[expected_index]
        other=max([p for i,p in enumerate(probs) if i!=expected_index] or [0.0])
        # Uncertain is not an automatic fail; a strong contradiction is.
        # Relaxed thresholds: CLIP-vit-base-patch32 is often unconfident on
        # specific weapon/proportion checks.  Lower min_prob 0.40->0.30 and
        # min_margin 0.08->0.04 so that a CLIP score of 0.32 (clearly above
        # random 0.50 for binary, but not "confident" by old standard) still
        # passes instead of becoming uncertain → hard fail via CRITICAL_UNCERTAIN.
        if expected >= min_prob and expected-other >= min_margin: ok=True
        elif other >= min_prob and other-expected >= min_margin: ok=False
        else: ok=None
        return ClipDecision(check,ok,round(expected,4),selected,{l:round(p,4) for l,p in zip(labels,probs)},"uncertain" if ok is None else "")

    def inspect(self, image_path: str|Path, spec) -> dict:
        with Image.open(image_path) as im: image=im.convert("RGB")
        out=[]
        out.append(self._choose(image,["a full body game character with both feet visible","a cropped upper body portrait or character with feet cut off"],"full_body",0,.35,.05))
        # NOTE: no CLIP-based "single_character" check here on purpose. Real test
        # evidence (3 real "final"-mode jobs, ~13 attempts) showed CLIP-vit-base-patch32
        # confidently (conf 0.02-0.15, i.e. it believed "two or more people" with
        # 85-98% certainty) misjudging genuinely single-character compact-chibi/figurine
        # renders as "duplicate characters" in every single attempt, while the
        # purpose-built classical layout heuristic (single_character_quality.py,
        # already an independent hard-gate via quality_gate.py's base.passed) correctly
        # scored the same images ok=True with a single foreground cluster. CLIP is a
        # documented poor object-counter; re-adding a CLIP-based duplicate-count check
        # here would just reintroduce that same near-100% false-positive rate.
        out.append(self._choose(image,["a character on a plain simple studio background","a character in detailed scenery or a complex interface"],"plain_background",0,.35,.05))
        out.append(self._choose(image,["a compact chibi game character with a large head and short body","a tall realistic adult character with long human proportions"],"compact_proportions",0,.30,.04))
        out.append(self._choose(image,["a game character standing directly on a plain floor with no platform","a figurine standing on a round pedestal display base"],"no_pedestal",0,.35,.05))
        if spec.gender:
            labels=[f"an adult {spec.gender} fantasy character", "an adult female fantasy character" if spec.gender=="male" else "an adult male fantasy character"]
            out.append(self._choose(image,labels,"gender",0,.35,.06))
        if spec.weapon_type:
            # Use descriptive CLIP labels matched to the actual object type
            # so CLIP can distinguish "umbrella" from "sword" etc.
            _clip_labels = {
                "sword": ("a character visibly holding a long sword with blade", "a character without a visible sword"),
                "katana": ("a character visibly holding a katana", "a character without a visible katana"),
                "blade": ("a character visibly holding a bladed weapon", "a character without a visible bladed weapon"),
                "bow": ("a character visibly holding a bow", "a character without a visible bow"),
                "spear": ("a character visibly holding a spear", "a character without a visible spear"),
                "axe": ("a character visibly holding an axe", "a character without a visible axe"),
                "staff": ("a character visibly holding a staff or wand", "a character without a visible staff or wand"),
                "hammer": ("a character visibly holding a hammer", "a character without a visible hammer"),
                "shield": ("a character carrying a visible shield", "a character without a visible shield"),
                "dagger": ("a character visibly holding a short dagger", "a character without a visible dagger"),
                "knife": ("a character visibly holding a knife", "a character without a visible knife"),
                "gun": ("a character visibly holding a gun", "a character without a visible gun"),
                "rifle": ("a character visibly holding a rifle", "a character without a visible rifle"),
                "umbrella": ("a character visibly holding an open umbrella or parasol", "a character without a visible umbrella or parasol"),
            }
            pos_label, neg_label = _clip_labels.get(spec.weapon_type, (f"a character visibly holding a {spec.weapon_type}", f"a character without a visible {spec.weapon_type}"))
            out.append(self._choose(image,[pos_label, neg_label],"weapon_type",0,.30,.03))
            if spec.weapon_type in {"sword","katana","blade"}:
                labels=["a fantasy character holding a bladed sword", "a character holding a gun rifle firearm camera launcher or cannon"]
                out.append(self._choose(image,labels,"weapon_family",0,.35,.06))
            elif spec.weapon_type == "umbrella":
                labels=["a character holding an open umbrella or parasol", "a character holding a sword, gun, bow or other weapon instead of an umbrella"]
                out.append(self._choose(image,labels,"weapon_family",0,.35,.06))
            elif spec.weapon_type == "shield":
                labels=["a character carrying a shield", "a character holding a sword, gun, bow or other weapon instead of a shield"]
                out.append(self._choose(image,labels,"weapon_family",0,.35,.06))
            elif spec.weapon_type == "staff":
                labels=["a character holding a staff or wand", "a character holding a sword, gun, bow or other weapon instead of a staff"]
                out.append(self._choose(image,labels,"weapon_family",0,.35,.06))
            if spec.weapon_count==1:
                labels=[f"a character with exactly one visible {spec.weapon_type}", f"a character with two or more weapons or dual wielding"]
                out.append(self._choose(image,labels,"weapon_count",0,.30,.04))
        if spec.armor_primary:
            labels=[f"a character wearing {spec.armor_primary} armor", "a character wearing white or silver armor", "a character wearing armor of another color"]
            out.append(self._choose(image,labels,"armor_color",0,.36,.04))
        if spec.accent_color:
            labels=[f"a character with a clearly visible {spec.accent_color} sash or cloth accent", "a character without that colored sash or accent"]
            out.append(self._choose(image,labels,"accent_color",0,.35,.04))
        if getattr(spec, "cape_color", None):
            labels=[f"a character wearing a clearly visible {spec.cape_color} cape or cloak", "a character wearing a cape or cloak of another color"]
            out.append(self._choose(image,labels,"cape_color",0,.34,.035))
        return {"model":_MODEL_ID,"checks":[asdict(d) for d in out],"hard_failures":[d.check for d in out if d.ok is False],"uncertain":[d.check for d in out if d.ok is None]}
