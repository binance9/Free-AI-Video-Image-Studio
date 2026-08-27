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
        if expected >= min_prob and expected-other >= min_margin: ok=True
        elif other >= min_prob and other-expected >= min_margin: ok=False
        else: ok=None
        return ClipDecision(check,ok,round(expected,4),selected,{l:round(p,4) for l,p in zip(labels,probs)},"uncertain" if ok is None else "")

    def inspect(self, image_path: str|Path, spec) -> dict:
        with Image.open(image_path) as im: image=im.convert("RGB")
        out=[]
        out.append(self._choose(image,["a full body game character with both feet visible","a cropped upper body portrait or character with feet cut off"],"full_body",0,.42,.07))
        out.append(self._choose(image,["one single person only","two or more people or duplicate characters"],"single_character",0,.42,.07))
        out.append(self._choose(image,["a character on a plain simple studio background","a character in detailed scenery or a complex interface"],"plain_background",0,.40,.06))
        out.append(self._choose(image,["a compact chibi game character with a large head and short body","a tall realistic adult character with long human proportions"],"compact_proportions",0,.40,.05))
        out.append(self._choose(image,["a game character standing directly on a plain floor with no platform","a figurine standing on a round pedestal display base"],"no_pedestal",0,.40,.06))
        if spec.gender:
            labels=[f"an adult {spec.gender} fantasy character", "an adult female fantasy character" if spec.gender=="male" else "an adult male fantasy character"]
            out.append(self._choose(image,labels,"gender",0,.42,.08))
        if spec.weapon_type:
            labels=[f"a character visibly holding a {spec.weapon_type}", f"a character without a visible {spec.weapon_type}"]
            out.append(self._choose(image,labels,"weapon_type",0,.38,.05))
            if spec.weapon_type in {"sword","katana","blade"}:
                labels=["a fantasy character holding a bladed sword", "a character holding a gun rifle firearm camera launcher or cannon"]
                out.append(self._choose(image,labels,"weapon_family",0,.42,.08))
            if spec.weapon_count==1:
                labels=[f"a character with exactly one visible {spec.weapon_type}", f"a character with two or more weapons or dual wielding"]
                out.append(self._choose(image,labels,"weapon_count",0,.38,.05))
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
