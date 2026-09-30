"""Local text-to-image, edit, and reference-preserving image generation."""
from __future__ import annotations

import inspect
import io
import json
import gc
import re
import secrets
import tempfile
import time
import unicodedata
from pathlib import Path
from threading import Lock, local

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from app.core.shared_services import JobCancelled
from app.core.prompt_contract import build_priority_prompt, compact_core_requirements, fit_prompt_to_pipeline, prompt_contract_meta
from app.modules.ga_brain.model_client import OllamaClient
from .upscale import finalize_pil, generation_dimensions, target_dimensions, upscale_realesrgan

_VIETNAMESE = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
_REFERENCE = re.compile(r"(dựa\s*(?:theo|trên)|theo\s*ảnh|tham\s*khảo\s*ảnh|based\s+on|use\s+(?:this|the)\s+(?:image|photo)|from\s+(?:this|the)\s+(?:image|photo))", re.I)
_SWORD = re.compile(r"(cầm\s*kiếm|thêm\s*kiếm|đổi\s*vũ\s*khí\s*thành\s*kiếm|hold(?:ing|s)?\s+(?:a\s+)?sword|add\s+(?:a\s+)?sword|replace\s+the\s+weapon)", re.I)
_FULL_BODY = re.compile(r"(toàn\s*thân|toan\s*than|full(?:-|\s*)body)", re.I)
_WING = re.compile(r"(cánh|canh|wing(?:s)?|angel wing(?:s)?|feather(?:s)?)", re.I)
_FEMALE = re.compile(r"\b(nữ|nu|female|woman|girl)\b", re.I)
_MALE = re.compile(r"\b(nam|male|man|boy)\b", re.I)
_WUXIA = re.compile(r"(kiếm\s*hiệp|kiem\s*hiep|wuxia|sword(?:s)?woman|sword(?:s)?man|swordswoman|swordsman)", re.I)
_ARCHER = re.compile(r"(cung\s*thủ|cung\s*thu|archer)", re.I)
_MULTI_COUNT = re.compile(r"\b(?:hai|ba|bon|2|3|4|two|three|four|couple|pair|group|duo|team)\b", re.I)
_SHEET_REQUEST = re.compile(r"(character\s*sheet|model\s*sheet|reference\s*sheet|turnaround|multi[-\s]*view|front.*side.*back|nhiều\s*góc|nhieu\s*goc|nhiều\s*view|nhieu\s*view)", re.I)

_GENERIC_SEMANTIC_PATTERNS = {
    "subject": [
        ("cat", r"\b(cat|m[eè]o)\b"), ("dog", r"\b(dog|ch[oó])\b"), ("bird", r"\b(bird|chim)\b"),
        ("horse", r"\b(horse|ng[uự]a)\b"), ("fish", r"\b(fish|c[aá])\b"), ("dragon", r"\b(dragon|r[oồ]ng)\b"),
        ("baby", r"\b(baby|em\s*b[eé])\b"), ("child", r"\b(child|kid|tr[eẻ])\b"), ("elderly person", r"\b(elderly|old person|ng[uườ]i gi[aà])\b"),
        ("car", r"\b(car|xe\s*h[oơ]i|[oô]\s*t[oô])\b"), ("motorcycle", r"\b(motorcycle|motorbike|xe\s*m[aá]y)\b"),
        ("truck", r"\b(truck|xe\s*t[aả]i)\b"), ("train", r"\b(train|t[aà]u\s*h[oỏ]a)\b"), ("boat", r"\b(boat|ship|thuy[eề]n|t[aà]u\s*bi[eể]n)\b"),
        ("airplane", r"\b(airplane|plane|m[aá]y\s*bay)\b"), ("helicopter", r"\b(helicopter|tr\w*c\s*th[aă]ng)\b"),
        ("robot", r"\b(robot)\b"), ("machine", r"\b(machine|m[aá]y\s*m[oó]c)\b"), ("engine", r"\b(engine|d[oộ]ng\s*c[oơ])\b"),
        ("gear", r"\b(gear|b[aá]nh\s*r[aă]ng|linh\s*ki[eệ]n)\b"), ("helmet", r"\b(helmet|m[uũ])\b"), ("hat", r"\b(hat|n[oó]n)\b"),
        ("shirt", r"\b(shirt|[aá]o)\b"), ("pants", r"\b(pants|qu[aầ]n)\b"), ("dress", r"\b(dress|v[aá]y)\b"),
        ("map", r"\b(map|b[aả]n\s*đ[oồ])\b"), ("moon", r"\b(moon|m[aặ]t\s*tr[aă]ng)\b"), ("sun", r"\b(sun|m[aặ]t\s*tr[oờ]i)\b"),
    ],
    "action": [
        ("holding", r"\b(holding|hold|c[aầ]m)\b"), ("wearing", r"\b(wearing|wear|m[aặ]c)\b"), ("driving", r"\b(driving|drive|l[aá]i)\b"),
        ("riding", r"\b(riding|ride|cưỡi)\b"), ("flying", r"\b(flying|fly|bay)\b"), ("standing", r"\b(standing|đứng)\b"),
        ("sitting", r"\b(sitting|ngồi)\b"), ("running", r"\b(running|chạy)\b"), ("lying", r"\b(lying|nằm)\b"),
    ],
    "object": [
        ("sword", r"\b(sword|ki[eế]m)\b"), ("bow", r"\b(bow|cung)\b"), ("gun", r"\b(gun|s[uú]ng)\b"),
        ("umbrella", r"\b(umbrella|ô)\b"), ("bag", r"\b(bag|t[uú]i)\b"),
    ],
    "color": [
        ("red", r"\b(red|đỏ)\b"), ("blue", r"\b(blue|xanh\s*dương|xanh\s*biển)\b"), ("green", r"\b(green|xanh\s*l[aá])\b"),
        ("yellow", r"\b(yellow|v[aà]ng)\b"), ("black", r"\b(black|đen)\b"), ("white", r"\b(white|trắng)\b"),
        ("silver", r"\b(silver|bạc)\b"), ("gold", r"\b(gold|v[aà]ng\s*kim)\b"), ("brown", r"\b(brown|nâu)\b"),
        ("pink", r"\b(pink|hồng)\b"), ("purple", r"\b(purple|tím)\b"), ("orange", r"\b(orange|cam)\b"),
    ],
    "weather": [
        ("rain", r"\b(rain|rainy|mưa)\b"), ("sunny", r"\b(sunny|nắng)\b"), ("cloudy", r"\b(cloudy|nhiều\s*m[aâ]y)\b"),
        ("storm", r"\b(storm|b[aã]o)\b"), ("snow", r"\b(snow|tuyết)\b"), ("fog", r"\b(fog|sương\s*mù)\b"),
    ],
    "time": [
        ("daytime", r"\b(day|ban\s*ng[aà]y)\b"), ("night", r"\b(night|ban\s*đ[eê]m)\b"),
        ("sunset", r"\b(sunset|ho[aà]ng\s*h[oô]n)\b"), ("sunrise", r"\b(sunrise|bình\s*minh)\b"),
    ],
    "scene": [
        ("forest", r"\b(forest|rừng)\b"), ("mountains", r"\b(mountain|núi)\b"), ("beach", r"\b(beach|bờ\s*biển)\b"),
        ("city", r"\b(city|thành\s*phố)\b"), ("village", r"\b(village|làng)\b"), ("factory", r"\b(factory|nhà\s*m[aá]y)\b"),
        ("room", r"\b(room|căn\s*phòng)\b"), ("sky", r"\b(sky|bầu\s*trời)\b"), ("river", r"\b(river|sông)\b"),
        ("lake", r"\b(lake|hồ)\b"), ("volcano", r"\b(volcano|núi\s*lửa)\b"),
        ("top-down map", r"\b(top[- ]?down|nhìn\s*từ\s*trên)\b"), ("isometric", r"\b(isometric)\b"),
    ],
}
_GENERIC_BOILERPLATE = re.compile(r"\b(?:render|subject|style|scene|image|picture|photo|create|generate|make|please|show|a|an|the)\b", re.I)

_STYLE_ALIASES = {
    "ảnh thật": "photo",
    "anh that": "photo",
    "photoreal": "photo",
    "realistic": "photo",
}

_STYLE = {
    "photo": "realistic, photoreal, real-person proportions, natural anatomy, natural skin texture, professional photography, natural lighting",
    "cartoon3d": "polished 3D cartoon, clean shapes, expressive, cinematic soft lighting",
    "anime": "anime illustration, crisp line art, detailed lighting, clean composition",
    "cinematic": "cinematic concept art, dramatic light, strong composition, detailed atmosphere",
    "illustration": "professional digital illustration, refined colors, clean composition",
    "product": "professional product photograph, accurate proportions, clean studio lighting",
    "fantasy": "high-detail fantasy art, cinematic lighting, rich environment",
}
CHARACTER_NEGATIVE_PROMPT = (
    "chibi, cartoon, anime, painted illustration, doll, toy, redesign, deformed face, face distortion, "
    "asymmetrical eyes, bad mouth, blurry face, anatomy deformation, bad anatomy, extra limbs, "
    "costume replacement, style drift, floating weapon, hand deformation, deformed hands, bad hands"
)

CHARACTER_QUALITY_PRESETS = {
    "REALISTIC_CHARACTER": (
        "EXACTLY ONE CHARACTER, single centered primary subject, three-quarter body framing, entire head and hands visible, clear face, "
        "balanced facial proportions, attractive youthful adult face, symmetric eyes, "
        "natural mouth and coherent nose, clean natural skin, realistic lighting, coherent hair, real-person proportions, correct anatomy, coherent torso, "
        "correct limb count and hands, natural pose, readable costume, "
        "strong character identity"
    ),
    "FANTASY_GAME_CHARACTER": (
        "EXACTLY ONE FANTASY CHARACTER, single centered subject, clear visible attractive face, balanced facial "
        "proportions, symmetric eyes, natural mouth, coherent hair, stylized but proportional anatomy, readable "
        "costume, coherent torso, correct limb count and hands, natural pose, strong class identity, polished game render"
    ),
    "GENERAL_IMAGE": (
        "EXACTLY ONE PRIMARY SUBJECT unless multiple subjects are explicitly requested, clear composition, "
        "coherent geometry, accurate details, suitable lighting and camera"
    ),
}

SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
DREAMSHAPER_MODEL = "Lykon/dreamshaper-8"
FLUX_MODEL = "black-forest-labs/FLUX.1-dev"
FLUX_SCHNELL_MODEL = "black-forest-labs/FLUX.1-schnell"

# FLUX is a 12B MMDiT flow-matching model: no negative_prompt, guidance ~3.5,
# steps 20-28 (dev) or 4 (schnell), native 1024x1024, bfloat16.
FLUX_MODELS = frozenset({FLUX_MODEL, FLUX_SCHNELL_MODEL})

CHARACTER_GENERATION_NEGATIVE = (
    "multiple people, two women, duplicate person, duplicated person, cloned subject, extra face, asymmetrical eyes, warped face, "
    "deformed mouth, bad anatomy, extra limbs, bad hands, generic stock-photo composition, "
    "broken hands, distorted body, extreme close-up, cropped head, fashion catalog, split composition, split screen, collage, "
    "character sheet, model sheet, reference sheet, turnaround sheet, front view and side view, front view, side view, back view, multi view lineup, pose lineup, lineup"
)


def _searchable(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().split())


def _is_character_generation(prompt: str) -> bool:
    text = _searchable(prompt)
    return bool(re.search(
        r"\b(?:nhan vat|character|nu|female|woman|girl|male|man|boy|cung thu|archer|kiem si|warrior|hero|portrait|full body)\b",
        text,
    ))


def _has_explicit_character_count(prompt: str) -> bool:
    text = _searchable(prompt)
    return bool(re.search(r"\b(?:hai|ba|bon|2|3|4|two|three|four|couple|pair|group|duo|team)\b", text))


def _character_preset(prompt: str, style: str) -> str:
    text = _searchable(prompt)
    fantasy = style == "fantasy" or any(
        token in text for token in ("fantasy", "game", "tien hiep", "cung thu", "archer", "warrior", "hero")
    )
    return "FANTASY_GAME_CHARACTER" if fantasy else "REALISTIC_CHARACTER"


def _extract_character_constraints(original_prompt: str, translated_prompt: str, style: str) -> dict:
    source = f"{original_prompt or ''} {translated_prompt or ''}".strip()
    searchable = _searchable(source)
    female = bool(_FEMALE.search(source))
    male = bool(_MALE.search(source))
    archer = bool(_ARCHER.search(source))
    sword = bool(_SWORD.search(source)) or (' sword ' in f' {searchable} ') or (' kiem ' in f' {searchable} ')
    wuxia = bool(_WUXIA.search(source)) or (sword and any(tok in searchable for tok in (' wuxia ', ' kiem hiep ', ' kiem si ', ' warrior ', ' hero ')))
    full_body = bool(_FULL_BODY.search(source)) or any(tok in searchable for tok in (' full body ', ' toan than '))
    multi = bool(_MULTI_COUNT.search(source))
    single = not multi
    photoreal = style == 'photo' or any(tok in searchable for tok in (' photo ', ' photorealistic ', ' realistic ', ' anh that '))
    wings_requested = bool(_WING.search(source))
    sheet_requested = bool(_SHEET_REQUEST.search(source))
    count_phrase = 'use exactly the requested character count; no duplicates' if multi else 'EXACTLY ONE CHARACTER ONLY'
    identity_parts = []
    if female and not male:
        identity_parts.append('female')
    elif male and not female:
        identity_parts.append('male')
    else:
        identity_parts.append('adult')
    if archer:
        identity_parts.append('archer')
    elif sword and wuxia:
        identity_parts.append('wuxia swordswoman' if female and not male else 'wuxia swordsman' if male and not female else 'wuxia sword warrior')
    elif sword:
        identity_parts.append('sword fighter')
    elif wuxia:
        identity_parts.append('wuxia warrior')
    else:
        identity_parts.append('character')
    identity_phrase = ' '.join(identity_parts)
    return {
        'female': female, 'male': male, 'archer': archer, 'sword': sword, 'wuxia': wuxia,
        'full_body': full_body, 'multi': multi, 'single': single, 'photoreal': photoreal,
        'wings_requested': wings_requested, 'disallow_wings': not wings_requested,
        'sheet_requested': sheet_requested, 'anti_sheet': single and not sheet_requested,
        'count_phrase': count_phrase, 'identity_phrase': identity_phrase,
    }


def _compose_character_prompt(clean_prompt: str, style: str, constraints: dict) -> tuple[str, str]:
    """Build a compact prompt that stays safely inside CLIP's real window.

    For CLIP-backed SD/SDXL pipelines the 77-token context is architectural;
    increasing a numeric setting does not create more context.  Therefore the
    user's count/identity/action/framing are encoded first in short canonical
    phrases. Cosmetic prose is last and expendable.
    """
    prompt_bits: list[str] = []
    prompt_bits.append('requested count only' if constraints['multi'] else 'one person only')
    prompt_bits.append(constraints['identity_phrase'])
    if constraints['sword']:
        prompt_bits.append('holding one visible sword')
    if constraints['archer']:
        prompt_bits.append('holding one visible bow')
    if constraints['full_body']:
        prompt_bits.append('full body standing')
        prompt_bits.append('head hands and feet visible')
        if constraints['sword'] or constraints['archer']:
            prompt_bits.append('weapon visible')
    else:
        prompt_bits.append('single pose')
    if constraints.get('anti_sheet'):
        prompt_bits.append('single scene')
        prompt_bits.append('single camera view')
    if constraints['disallow_wings']:
        prompt_bits.append('no wings')
    if constraints['photoreal']:
        prompt_bits += ['photorealistic', 'real-person proportions', 'natural skin', 'realistic light']
    else:
        prompt_bits.append(_STYLE.get(style, _STYLE['photo']))

    # Preserve a tiny amount of user-specific detail without allowing verbose
    # translation boilerplate to push sword/full-body beyond the CLIP window.
    extra = compact_core_requirements(clean_prompt, max_words=6)
    extra = re.sub(r'\b(?:create|make|generate|image|picture|photo|photorealistic|realistic|full\s+body|whole\s+body|female|male|woman|man|girl|boy|wuxia|swordswoman|swordsman|warrior|holding|hold|one|sword|bow|standing)\b', '', extra, flags=re.I)
    extra = re.sub(r'\s+', ' ', extra).strip(' ,.;')
    if extra and len(extra.split()) >= 2:
        prompt_bits.append(extra)

    positive = ', '.join(dict.fromkeys(bit.strip(' ,.;') for bit in prompt_bits if bit and bit.strip(' ,.;')))

    # Negative prompt is intentionally compact too. Long negatives can be
    # truncated just like positives and silently lose the blockers we need.
    negative_parts: list[str] = []
    if constraints.get('anti_sheet'):
        negative_parts += ['character sheet', 'lineup', 'multi-view', 'multiple people', 'duplicate person']
    if constraints['sword']:
        negative_parts += ['missing sword', 'wrong weapon']
    if constraints['archer']:
        negative_parts += ['missing bow', 'wrong weapon']
    if constraints['full_body']:
        negative_parts += ['close-up', 'upper body only', 'cropped feet']
    if constraints['disallow_wings']:
        negative_parts += ['wings']
    if constraints['photoreal']:
        negative_parts += ['3d render', 'cgi', 'anime', 'cartoon', 'chibi']
    if constraints['female'] and not constraints['male']:
        negative_parts += ['male']
    if constraints['male'] and not constraints['female']:
        negative_parts += ['female']
    negative_parts += ['extra limbs', 'bad hands']
    negative = ', '.join(dict.fromkeys(negative_parts))
    return positive, negative


def _strip_prompt_boilerplate(text: str) -> str:
    value = re.sub(r"[\r\n\t]+", " ", str(text or ""))
    value = re.sub(r"[:|]+", " ", value)
    value = _GENERIC_BOILERPLATE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip(" ,.;")


def _collect_semantic_tags(source: str) -> dict[str, list[str]]:
    text = _searchable(source)
    found: dict[str, list[str]] = {k: [] for k in _GENERIC_SEMANTIC_PATTERNS}
    for bucket, entries in _GENERIC_SEMANTIC_PATTERNS.items():
        for label, pattern in entries:
            if re.search(pattern, text, re.I):
                if label not in found[bucket]:
                    found[bucket].append(label)
    return found


def _compose_general_prompt(original_prompt: str, clean_prompt: str, style: str) -> tuple[str, str]:
    source = f"{original_prompt or ''} {clean_prompt or ''}".strip()
    normalized = _strip_prompt_boilerplate(clean_prompt or original_prompt or source)
    core = compact_core_requirements(normalized, max_words=18) or compact_core_requirements(source, max_words=18)
    tags = _collect_semantic_tags(source)

    parts: list[str] = []
    if core:
        parts.append(core)
    # Append only a few high-value semantic tags actually found in the prompt.
    for bucket in ("subject", "object", "action", "color", "weather", "time", "scene"):
        values = tags.get(bucket) or []
        if not values:
            continue
        snippet = ', '.join(values[:3])
        if snippet and snippet.lower() not in (parts[0].lower() if parts else ""):
            parts.append(snippet)

    style_phrase = {
        'photo': 'photorealistic, natural lighting',
        'anime': 'anime illustration',
        'cartoon3d': 'stylized 3d cartoon render',
        'cinematic': 'cinematic lighting',
        'illustration': 'digital illustration',
        'product': 'product-style render',
        'fantasy': 'fantasy art',
    }.get(style, 'photorealistic, natural lighting')
    parts.append(style_phrase)

    positive = ', '.join(dict.fromkeys(p.strip(' ,.;') for p in parts if p and p.strip(' ,.;')))

    negative_parts: list[str] = ['low detail', 'blurry', 'distorted', 'deformed']
    if style == 'photo':
        negative_parts += ['cartoon', 'anime', 'cgi']
    elif style == 'anime':
        negative_parts += ['photorealistic photo', 'cgi']
    elif style == 'cartoon3d':
        negative_parts += ['flat photo', '2d sketch']
    negative = ', '.join(dict.fromkeys(negative_parts))
    return positive, negative


def _finalize_full_body_character(image: Image.Image, target_size: str) -> bytes:
    """Preserve the complete square character render on wide/tall requested output.

    ImageOps.fit crops. For full-body work that can remove feet or the weapon.
    Instead keep the whole render and extend the surrounding background with a
    soft blurred version of the same image.
    """
    dims = target_dimensions(target_size)
    source = image.convert('RGB')
    if source.size == dims:
        out = source
    else:
        bg = ImageOps.fit(source, dims, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).filter(ImageFilter.GaussianBlur(24))
        fg = ImageOps.contain(source, dims, method=Image.Resampling.LANCZOS)
        x = (dims[0] - fg.width) // 2
        y = (dims[1] - fg.height) // 2
        bg.paste(fg, (x, y))
        out = bg
    buffer = io.BytesIO()
    out.save(buffer, 'PNG', optimize=True)
    return buffer.getvalue()


def generation_mode(*, has_image: bool, prompt: str = "", has_mask: bool = False) -> str:
    if not has_image:
        return "TEXT2IMG"
    searchable = _searchable(prompt)
    reference = bool(_REFERENCE.search(prompt or "")) or any(
        phrase in searchable for phrase in ("dua theo anh", "theo anh nay", "tham khao anh", "based on this image")
    )
    return "IMAGE_REFERENCE" if reference else "IMAGE_EDIT"


def normalize_style(style: str) -> str:
    value = (style or "photo").strip().lower()
    return _STYLE_ALIASES.get(value, value if value in _STYLE else "photo")


class LocalImageService:
    def __init__(self, model_id: str, model_dir: str | Path):
        self.model_id = model_id
        self.model_dir = Path(model_dir).resolve()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._text_pipe = self._img_pipe = self._inpaint_pipe = None
        self._lock, self._run_lock = Lock(), Lock()
        self._translator = OllamaClient()
        self._active_model = None
        self._metadata = local()

    def generate(self, prompt: str, style: str = "photo", size: str = "1536x1024", quality: str = "high", *, backend: str = "auto", steps: int | None = None, cancel_event=None, progress=None) -> bytes:
        started = time.perf_counter()
        self._check_cancel(cancel_event)
        style = normalize_style(style)
        print("AIVF_IMAGE_MODE|TEXT2IMG|input_image_used=false", flush=True)
        if progress:
            progress(8, "TEXT2IMG", "Loading text-to-image pipeline")
        model_id = self._select_model("text", style, prompt, backend=backend)
        print(f"AIVF_IMAGE_MODEL|mode=TEXT2IMG|model={model_id}", flush=True)
        pipe = self._text_pipeline(model_id)
        character_constraints = _extract_character_constraints(prompt, prompt, style) if _is_character_generation(prompt) else {}
        width, height = self._generation_dimensions(size, model_id)
        preserve_full_body = bool(character_constraints.get("anti_sheet") and character_constraints.get("full_body"))
        if preserve_full_body:
            # A wide native canvas strongly biases SDXL toward model sheets / multi-view lineups.
            # Generate a square single-subject composition first, then extend the background
            # to the requested output aspect ratio without cropping the person.
            if model_id in FLUX_MODELS:
                width, height = 1024, 1024
            elif model_id == SDXL_MODEL:
                width, height = 1024, 1024
            elif model_id == DREAMSHAPER_MODEL:
                width, height = 768, 768
            else:
                width, height = 640, 640
            print(f"AIVF_CHARACTER_CANVAS|single_full_body=true|native={width}x{height}|target={size}", flush=True)
        # FLUX dev: 20-28 steps, schnell: 4 steps; SDXL: 20-28; others: 16-24
        if model_id in FLUX_MODELS:
            if model_id == FLUX_SCHNELL_MODEL:
                steps = 4 if quality == "high" else 4
            else:
                steps = 28 if quality == "high" else 20
        else:
            steps = (28 if model_id == SDXL_MODEL else 24) if quality == "high" else (20 if model_id == SDXL_MODEL else 16)
        if steps is not None:
            steps = max(8, min(40, int(steps)))  # clamp to safe range
        positive, negative = self.build_prompt(prompt, style, "TEXT2IMG")
        positive_fit = fit_prompt_to_pipeline(positive, pipe)
        negative_fit = fit_prompt_to_pipeline(negative, pipe)
        positive, negative = positive_fit.text, negative_fit.text
        print(
            f"AIVF_PROMPT_CONTRACT|mode=TEXT2IMG|tokens={positive_fit.token_count}|limit={positive_fit.token_limit}|truncated={str(positive_fit.truncated).lower()}",
            flush=True,
        )
        print(f"AIVF_PROMPT_FINAL|positive={positive}", flush=True)
        print(f"AIVF_NEGATIVE_FINAL|negative={negative}", flush=True)
        import torch
        torch.cuda.reset_peak_memory_stats()
        base_seed = secrets.randbelow(2**31 - 3)
        character_job = _is_character_generation(prompt) or _is_character_generation(positive)
        candidates = []
        current_positive, current_negative = positive, negative
        with self._run_lock:
            for attempt in range(3):  # initial + at most two adaptive retries
                seed = base_seed + attempt
                attempt_positive_fit = fit_prompt_to_pipeline(current_positive, pipe)
                attempt_negative_fit = fit_prompt_to_pipeline(current_negative, pipe)
                current_positive = attempt_positive_fit.text
                current_negative = attempt_negative_fit.text
                if model_id in FLUX_MODELS:
                    # FLUX is a flow-matching model: guidance 3.5 (dev), 0.0 (schnell)
                    # FLUX doesn't use negative_prompt; omit it
                    flux_guidance = 0.0 if model_id == FLUX_SCHNELL_MODEL else 3.5
                    kwargs = dict(
                        prompt=current_positive, width=width, height=height,
                        num_inference_steps=steps, guidance_scale=flux_guidance,
                        generator=torch.Generator(device="cuda").manual_seed(seed),
                    )
                else:
                    kwargs = dict(
                        prompt=current_positive, negative_prompt=current_negative, width=width, height=height,
                        num_inference_steps=steps, guidance_scale=7.0 if model_id == SDXL_MODEL else 7.5,
                        generator=torch.Generator(device="cuda").manual_seed(seed),
                    )
                self._attach_cancel_callback(pipe, kwargs, steps, cancel_event, progress)
                output = pipe(**kwargs).images[0].convert("RGB")
                qa = self._character_visual_quality(output, style, expected=prompt) if character_job else {
                    "supported": False,
                    "pass": not (style == "photo" and self._looks_cartoon(output)),
                    "score": 1 if not (style == "photo" and self._looks_cartoon(output)) else 0,
                    "reason": "photo style drift" if style == "photo" and self._looks_cartoon(output) else "metadata-only pass",
                }
                candidates.append({
                    "image": output, "qa": qa, "seed": seed,
                    "prompt": current_positive, "negative": current_negative, "attempt": attempt + 1,
                })
                print(f"AIVF_CHARACTER_QA|attempt={attempt + 1}|result={qa}", flush=True)
                if qa.get("pass"):
                    break
                if attempt < 2:
                    if progress:
                        progress(25, "CHARACTER QUALITY RETRY", qa.get("reason", "visual quality gate failed"))
                    current_positive, current_negative = self._adaptive_retry_prompt(
                        positive, negative, qa, attempt + 1, style
                    )
        selected = max(candidates, key=lambda item: (bool(item["qa"].get("pass")), int(not item["qa"].get("looks_character_sheet", False)), item["qa"].get("score", 0), item.get("attempt", 0)))
        output = selected["image"]
        self._metadata.value = {
            "mode": "TEXT2IMG", "backend": backend, "model": model_id,
            "final_prompt": selected["prompt"], "negative_prompt": selected["negative"],
            "seed": selected["seed"], "strength": None, "attempt_count": len(candidates),
            "quality_gate": selected["qa"], "generation_seconds": round(time.perf_counter() - started, 3),
            "vram_peak_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            "native_resolution": [width, height],
            "prompt_contract": prompt_contract_meta(module="tao_anh_ai", fit=fit_prompt_to_pipeline(selected["prompt"], pipe), source_words=len((prompt or "").split())),
        }
        self._check_cancel(cancel_event)
        return _finalize_full_body_character(output, size) if preserve_full_body else finalize_pil(output, size)

    def edit(self, image_path: str | Path, prompt: str, style: str = "photo", size: str = "1536x1024", quality: str = "high", *, mask_path: str | Path | None = None, strength: float | None = None, mode: str | None = None, steps: int | None = None, cancel_event=None, progress=None) -> bytes:
        started = time.perf_counter()
        self._check_cancel(cancel_event)
        mode = mode or generation_mode(has_image=True, prompt=prompt, has_mask=mask_path is not None)
        if mode not in {"IMAGE_EDIT", "IMAGE_REFERENCE"}:
            raise ValueError(f"Invalid image-input mode: {mode}")
        style = normalize_style(style)
        use_inpaint = mask_path is not None
        image_path = Path(image_path)
        if not image_path.is_file():
            raise ValueError("Input image is missing; refusing to run image edit without its source image")
        print(
            f"AIVF_IMAGE_MODE|{mode}|input_image_used=true|pipeline={'INPAINT' if use_inpaint else 'PRESERVE_IMG2IMG'}",
            flush=True,
        )
        if progress:
            progress(8, mode, "Loading inpaint pipeline" if use_inpaint else "Loading preserve img2img pipeline")
        model_id = self._select_model("inpaint" if use_inpaint else "image", style, prompt)
        print(f"AIVF_IMAGE_MODEL|mode={mode}|model={model_id}", flush=True)
        pipe = self._inpaint_pipeline(model_id) if use_inpaint else self._image_pipeline(model_id)
        width, height = self._generation_dimensions(size, model_id)
        with Image.open(image_path) as source:
            init_image = ImageOps.pad(source.convert("RGB"), (width, height), Image.Resampling.LANCZOS,
                                      color=(255, 255, 255), centering=(0.5, 0.5))
        mask_image = None
        if mask_path is not None:
            with Image.open(mask_path) as mask:
                mask_image = ImageOps.pad(mask.convert("L"), (width, height), Image.Resampling.NEAREST,
                                          color=0, centering=(0.5, 0.5))
        if model_id in FLUX_MODELS:
            if model_id == FLUX_SCHNELL_MODEL:
                steps = 4
            else:
                steps = 24 if quality == "high" else 16
        else:
            steps = 26 if quality == "high" else 18
        if steps is not None:
            steps = max(8, min(40, int(steps)))  # clamp to safe range
        positive, negative = self.build_prompt(prompt, style, mode)
        positive_fit = fit_prompt_to_pipeline(positive, pipe)
        negative_fit = fit_prompt_to_pipeline(negative, pipe)
        positive, negative = positive_fit.text, negative_fit.text
        print(
            f"AIVF_PROMPT_CONTRACT|mode={mode}|tokens={positive_fit.token_count}|limit={positive_fit.token_limit}|truncated={str(positive_fit.truncated).lower()}",
            flush=True,
        )
        strength_class, default_strength = self._strength_policy(prompt, mode, use_inpaint)
        edit_strength = default_strength if strength is None else float(strength)
        edit_strength = min(max(edit_strength, 0.12), 0.65)
        import torch
        torch.cuda.reset_peak_memory_stats()
        base_seed = secrets.randbelow(2**31 - 3)
        candidates = []
        current_positive, current_negative, current_strength = positive, negative, edit_strength
        with self._run_lock:
            for attempt in range(3):
                seed = base_seed + attempt
                attempt_positive_fit = fit_prompt_to_pipeline(current_positive, pipe)
                attempt_negative_fit = fit_prompt_to_pipeline(current_negative, pipe)
                current_positive = attempt_positive_fit.text
                current_negative = attempt_negative_fit.text
                if model_id in FLUX_MODELS:
                    flux_guidance = 0.0 if model_id == FLUX_SCHNELL_MODEL else 3.5
                    kwargs = dict(
                        prompt=current_positive, image=init_image,
                        strength=current_strength, num_inference_steps=steps,
                        guidance_scale=flux_guidance,
                        generator=torch.Generator(device="cuda").manual_seed(seed),
                    )
                else:
                    kwargs = dict(
                        prompt=current_positive, negative_prompt=current_negative, image=init_image,
                        strength=current_strength, num_inference_steps=steps, guidance_scale=6.5,
                        generator=torch.Generator(device="cuda").manual_seed(seed),
                    )
                if mask_image is not None:
                    kwargs["mask_image"] = mask_image
                self._attach_cancel_callback(pipe, kwargs, steps, cancel_event, progress)
                output = pipe(**kwargs).images[0].convert("RGB")
                if mask_image is not None:
                    output = Image.composite(output, init_image, mask_image)
                similarity = self._similarity(init_image, output)
                qa = self._edit_visual_quality(init_image, output, prompt, mode, similarity)
                candidates.append({
                    "image": output, "qa": qa, "seed": seed, "strength": current_strength,
                    "prompt": current_positive, "negative": current_negative, "attempt": attempt + 1,
                })
                print(f"AIVF_EDIT_QA|attempt={attempt + 1}|result={qa}", flush=True)
                if qa.get("pass"):
                    break
                if attempt < 2:
                    if progress:
                        progress(25, "PRESERVE QUALITY RETRY", qa.get("reason", "edit quality gate failed"))
                    current_positive = positive + ". STRICT IDENTITY PRESERVATION; only the requested element may change"
                    current_negative = "new identity, changed face, changed costume, changed colors, " + negative
                    if "identity" in str(qa.get("reason")) or "similarity" in str(qa.get("reason")):
                        current_strength = max(0.12, current_strength - 0.07)
                    elif "requested change" in str(qa.get("reason")):
                        current_strength = min(0.48, current_strength + 0.05)
        selected = max(candidates, key=lambda item: (bool(item["qa"].get("pass")), int(not item["qa"].get("looks_character_sheet", False)), item["qa"].get("score", 0), item.get("attempt", 0)))
        output = selected["image"]
        self._metadata.value = {
            "mode": mode, "backend": "auto", "model": model_id,
            "final_prompt": selected["prompt"], "negative_prompt": selected["negative"],
            "seed": selected["seed"], "strength": round(selected["strength"], 3),
            "strength_class": strength_class, "attempt_count": len(candidates),
            "quality_gate": selected["qa"], "generation_seconds": round(time.perf_counter() - started, 3),
            "vram_peak_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            "native_resolution": [width, height], "input_image_used": True,
            "prompt_contract": prompt_contract_meta(module="tao_anh_ai", fit=fit_prompt_to_pipeline(selected["prompt"], pipe), source_words=len((prompt or "").split())),
        }
        self._check_cancel(cancel_event)
        return finalize_pil(output, size)

    def build_prompt(self, prompt: str, style: str, mode: str) -> tuple[str, str]:
        original_prompt = prompt or ""
        clean = self._translate(prompt)
        style = normalize_style(style)
        style_text = _STYLE.get(style, _STYLE["photo"])
        negative = CHARACTER_NEGATIVE_PROMPT

        if mode in {"IMAGE_EDIT", "IMAGE_REFERENCE"}:
            style_text = "match the uploaded image original visual style and rendering"
            negative = negative.replace("cartoon, anime, painted illustration, ", "")
        elif style == "anime":
            negative = negative.replace("cartoon, anime, painted illustration, ", "")
        elif style == "cartoon3d":
            negative = negative.replace("cartoon, ", "")
        elif style in {"illustration", "fantasy", "cinematic"}:
            negative = negative.replace("painted illustration, ", "")

        if mode == "TEXT2IMG":
            is_character = _is_character_generation(original_prompt) or _is_character_generation(clean)
            if is_character:
                constraints = _extract_character_constraints(original_prompt, clean, style)
                positive, negative = _compose_character_prompt(clean, style, constraints)
            else:
                positive, negative = _compose_general_prompt(original_prompt, clean, style)
        else:
            preserve = (
                "Preservation: preserve the original character identity, face, body, costume, colors, pose and composition; "
                "only apply the requested change; no character redesign"
            )
            if mode == "IMAGE_REFERENCE":
                preserve = (
                    "Preservation: use the uploaded image as the dominant reference; preserve the original character identity, "
                    "face, body, costume, colors, pose and composition; only apply the requested change; no redesign or chibi"
                )
            sword_rule = "only add or replace the weapon with one sword in the existing hand" if _SWORD.search(prompt or "") else ""
            positive = build_priority_prompt(
                clean,
                mandatory=[sword_rule, preserve],
                quality=[style_text],
                max_words=58,
                core_max_words=28,
                core_label="REQUESTED EDIT",
            )
        return positive, negative

    def _translate(self, prompt: str) -> str:
        clean = (prompt or "").strip()
        if len(clean) < 3:
            raise ValueError("Image prompt is too short")
        return self._translator.translate_to_english(clean) if _VIETNAMESE.search(clean) else clean

    def _prompt(self, prompt: str, style: str) -> str:
        return self.build_prompt(prompt, style, "TEXT2IMG")[0]

    def _edit_prompt(self, prompt: str, style: str) -> str:
        return self.build_prompt(prompt, style, "IMAGE_EDIT")[0]

    @staticmethod
    def _similarity(source: Image.Image, output: Image.Image) -> float:
        a = source.convert("RGB").resize((128, 128), Image.Resampling.BILINEAR)
        b = output.convert("RGB").resize((128, 128), Image.Resampling.BILINEAR)
        rms = sum(ImageStat.Stat(ImageChops.difference(a, b)).rms) / 3.0
        return max(0.0, 1.0 - rms / 255.0)

    @staticmethod
    def _looks_cartoon(image: Image.Image) -> bool:
        sample = image.convert("RGB").resize((96, 96), Image.Resampling.BILINEAR)
        edges = ImageStat.Stat(sample.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
        saturation = ImageStat.Stat(sample.convert("HSV").getchannel("S")).mean[0]
        pixels = list(sample.get_flattened_data())
        flat_white = sum(1 for red, green, blue in pixels if min(red, green, blue) > 225 and max(red, green, blue) - min(red, green, blue) < 25) / len(pixels)
        return edges > 30 and (flat_white > 0.35 or saturation > 145)

    @staticmethod
    def _foreground_segment_count(image: Image.Image) -> int:
        sample = image.convert("RGB").resize((192, 192), Image.Resampling.BILINEAR)
        px = sample.load()
        w, h = sample.size
        border = []
        for x in range(w):
            border.append(px[x, 0])
            border.append(px[x, h - 1])
        for y in range(h):
            border.append(px[0, y])
            border.append(px[w - 1, y])
        bg = tuple(int(sum(c[i] for c in border) / max(1, len(border))) for i in range(3))
        active = []
        for x in range(w):
            count = 0
            for y in range(h):
                r, g, b = px[x, y]
                dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                if dist > 60:
                    count += 1
            active.append(count >= max(10, int(h * 0.18)))
        segments = 0
        run = 0
        min_run = max(8, int(w * 0.06))
        for flag in active:
            if flag:
                run += 1
            else:
                if run >= min_run:
                    segments += 1
                run = 0
        if run >= min_run:
            segments += 1
        return segments

    @classmethod
    def _looks_character_sheet(cls, image: Image.Image) -> bool:
        sample = image.convert("RGB").resize((192, 192), Image.Resampling.BILINEAR)
        pixels = list(sample.getdata())
        light_ratio = sum(1 for r, g, b in pixels if min(r, g, b) > 220 and max(r, g, b) - min(r, g, b) < 20) / max(1, len(pixels))
        segments = cls._foreground_segment_count(sample)
        return light_ratio > 0.30 and segments >= 3

    @staticmethod
    def _adaptive_retry_prompt(positive: str, negative: str, qa: dict, retry_number: int, style: str) -> tuple[str, str]:
        """Retry without turning a short CLIP prompt back into a long essay."""
        reason = str(qa.get("reason") or "").lower()
        fixes: list[str] = []
        extra_negative: list[str] = []
        if "person_count" in reason or "character sheet" in reason or "lineup" in reason:
            fixes += ["one person only", "single pose", "single scene"]
            extra_negative += ["character sheet", "lineup", "multi-view", "multiple people", "duplicate person"]
        if "face" in reason:
            fixes += ["clear face"]
            extra_negative += ["cropped face", "warped face"]
        if "photorealistic" in reason or "style" in reason:
            fixes += ["photorealistic", "natural skin"]
            extra_negative += ["cgi", "3d render", "illustration", "anime", "cartoon"]
        if "subject mismatch" in reason:
            fixes += ["match requested gender and class", "required weapon visible"]
            extra_negative += ["wrong gender", "wrong class", "missing weapon", "hidden weapon"]
        if "weapon" in reason or "sword" in reason:
            fixes += ["holding one visible sword"]
            extra_negative += ["wrong weapon", "missing sword", "hidden sword"]
        if "full body" in reason:
            fixes += ["full body standing", "head hands feet visible"]
            extra_negative += ["close-up", "portrait crop", "upper body only", "cropped feet"]
        if not fixes:
            fixes += ["one person only", "correct anatomy"]

        # The base prompt already contains all hard constraints. Append only a
        # few unique repair tokens; fit_prompt_to_pipeline still gets final say.
        repair = ', '.join(dict.fromkeys(fixes))
        merged_negative = ', '.join(dict.fromkeys([*extra_negative, *[x.strip() for x in negative.split(',') if x.strip()]]))
        return f"{positive}, repair {retry_number}, {repair}", merged_negative


    @staticmethod
    def _strength_policy(prompt: str, mode: str, has_mask: bool) -> tuple[str, float]:
        if mode == "IMAGE_REFERENCE":
            return "reference", 0.18
        text = _searchable(prompt)
        if re.search(r"\b(?:hoan toan|toan bo|redesign|transform completely|completely different style)\b", text):
            return "redesign", 0.55
        if re.search(r"\b(?:trang phuc|quan ao|background|costume|outfit|moderate)\b", text):
            return "moderate", 0.38
        if has_mask:
            return "masked-local", 0.32
        return "minor", 0.26

    def consume_metadata(self) -> dict:
        value = dict(getattr(self._metadata, "value", {}) or {})
        self._metadata.value = {}
        return value

    def _character_visual_quality(self, image: Image.Image, style: str, *, expected: str = "") -> dict:
        """Inspect rendered pixels; never infer a PASS from prompt text alone."""
        photo_failed = style == "photo" and self._looks_cartoon(image)
        temp_path = None
        try:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=self.model_dir) as temp:
                temp_path = Path(temp.name)
            image.save(temp_path, "PNG")
            result = self._translator.analyze_image(
                temp_path,
                "Inspect only visible pixels. Return ONLY compact JSON with keys: "
                "person_count (integer), face_clear (boolean), face_deformed (boolean), "
                "anatomy_ok (boolean), style_match (boolean), photorealistic (boolean), subject_match (boolean), "
                "full_body_visible (boolean), required_weapon_visible (boolean), wings_present (boolean), character_sheet_layout (boolean). "
                "Count every distinct person. A cropped/missing, "
                "mask-like, warped, or unreadable face means face_clear=false. full_body_visible is true only when the full figure is inside frame. "
                "required_weapon_visible is true only when the requested weapon is visibly present in hand. wings_present is true when any wing-like appendage is visible. "
                "character_sheet_layout is true for lineups, model sheets, turnaround views, or multiple poses/views of the same character. "
                f"subject_match is true only when visible gender, character class, and required weapon match this request: {expected!r}. "
                "Judge pixels first; do not assume the request is present.",
            )
            summary = str(result.get("summary") or "")
            match = re.search(r"\{[^{}]+\}", summary, re.S)
            if not result.get("available") or not match:
                expected_text = _searchable(expected)
                requires_full_body = bool(_FULL_BODY.search(expected or '')) or ' full body ' in f' {expected_text} ' or ' toan than ' in f' {expected_text} '
                looks_sheet = self._looks_character_sheet(image)
                reasons = []
                if photo_failed:
                    reasons.append('not photorealistic')
                if looks_sheet:
                    reasons.append('character sheet / lineup detected')
                if requires_full_body and looks_sheet:
                    reasons.append('single full-body scene missing')
                return {
                    "supported": False,
                    "pass": not reasons,
                    "score": 0 if reasons else 1,
                    "reason": '; '.join(reasons) if reasons else 'fallback pass',
                    "looks_character_sheet": looks_sheet,
                }
            parsed = json.loads(match.group(0))
            try:
                person_count = int(parsed.get("person_count", -1))
            except (TypeError, ValueError):
                person_count = -1
            face_clear = parsed.get("face_clear") is True
            face_deformed = parsed.get("face_deformed") is True
            photorealistic = parsed.get("photorealistic") is True
            subject_match = parsed.get("subject_match") is True
            anatomy_ok = parsed.get("anatomy_ok") is True
            style_match = parsed.get("style_match") is True
            full_body_visible = parsed.get("full_body_visible") is True
            required_weapon_visible = parsed.get("required_weapon_visible") is True
            wings_present = parsed.get("wings_present") is True
            character_sheet_layout = parsed.get("character_sheet_layout") is True
            neutral_result = self._translator.describe_character_image(temp_path) if expected else {}
            neutral_summary = str(neutral_result.get("summary") or "")
            neutral_text = _searchable(neutral_summary)
            expected_text = _searchable(expected)
            requires_full_body = bool(_FULL_BODY.search(expected or '')) or ' full body ' in f' {expected_text} ' or ' toan than ' in f' {expected_text} '
            requires_sword = bool(_SWORD.search(expected or '')) or ' sword ' in f' {expected_text} ' or ' kiem ' in f' {expected_text} '
            wings_forbidden = not bool(_WING.search(expected or ''))
            neutral_match = True
            if re.search(r"\b(?:cung thu|archer|bow)\b", expected_text):
                neutral_match = neutral_match and bool(re.search(r"\b(?:cung|bow|archer)\b", neutral_text))
            if re.search(r"\b(?:nu|female|woman|girl)\b", expected_text):
                neutral_match = neutral_match and bool(re.search(r"\b(?:nu|female|woman|girl)\b", neutral_text))
            if re.search(r"\b(?:nam|male|man|boy)\b", expected_text):
                neutral_match = neutral_match and bool(re.search(r"\b(?:nam|male|man|boy)\b", neutral_text))
            if requires_sword:
                neutral_match = neutral_match and bool(re.search(r"\b(?:kiem|sword|blade|katana)\b", neutral_text))
            subject_match = subject_match and neutral_match
            reasons = []
            if person_count != 1:
                reasons.append(f"person_count={person_count}")
            if not face_clear:
                reasons.append("face not clear")
            if face_deformed:
                reasons.append("face deformed")
            if not anatomy_ok:
                reasons.append("anatomy failed")
            if not style_match:
                reasons.append("style mismatch")
            if style == "photo" and (photo_failed or not photorealistic):
                reasons.append("not photorealistic")
            if requires_full_body and not full_body_visible:
                reasons.append("full body missing")
            if requires_sword and not required_weapon_visible:
                reasons.append("weapon missing")
            if wings_forbidden and wings_present:
                reasons.append("wings present")
            if character_sheet_layout:
                reasons.append("character sheet layout")
            if expected and not subject_match:
                reasons.append("subject mismatch")
            score = (3 if person_count == 1 else 0) + (2 if face_clear else 0) + (
                2 if not face_deformed else 0
            ) + (2 if anatomy_ok else 0) + (2 if style_match else 0) + (
                2 if style != "photo" or photorealistic else 0
            ) + (2 if not requires_full_body or full_body_visible else 0) + (
                2 if not requires_sword or required_weapon_visible else 0
            ) + (2 if not wings_forbidden or not wings_present else 0) + (3 if not character_sheet_layout else 0) + (3 if not expected or subject_match else 0)
            return {
                "supported": True,
                "pass": not reasons,
                "score": score,
                "reason": "; ".join(reasons) if reasons else "pass",
                "person_count": person_count,
                "face_clear": face_clear,
                "face_deformed": face_deformed,
                "photorealistic": photorealistic,
                "subject_match": subject_match,
                "anatomy_ok": anatomy_ok,
                "style_match": style_match,
                "full_body_visible": full_body_visible,
                "required_weapon_visible": required_weapon_visible,
                "wings_present": wings_present,
                "character_sheet_layout": character_sheet_layout,
                "neutral_description": neutral_summary,
                "neutral_subject_match": neutral_match,
            }
        except Exception as exc:
            return {
                "supported": False,
                "pass": not photo_failed,
                "reason": f"vision evaluator error: {exc}" if not photo_failed else "not photorealistic",
            }
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def _edit_visual_quality(self, source: Image.Image, output: Image.Image, prompt: str, mode: str, similarity: float) -> dict:
        """Compare source/output pixels side by side with the installed vision evaluator."""
        threshold = 0.72 if mode == "IMAGE_REFERENCE" else 0.50
        temp_path = None
        try:
            side = Image.new("RGB", (source.width * 2, source.height), "white")
            side.paste(source.convert("RGB"), (0, 0))
            side.paste(output.convert("RGB"), (source.width, 0))
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=self.model_dir) as temp:
                temp_path = Path(temp.name)
            side.save(temp_path, "PNG")
            result = self._translator.analyze_image(
                temp_path,
                "The LEFT half is the uploaded source and RIGHT half is the edited result. Return ONLY compact JSON: "
                '{"identity_preserved": boolean, "face_preserved": boolean, "costume_preserved": boolean, '
                '"style_preserved": boolean, "requested_change_applied": boolean, "person_count": integer}. '
                f"Requested change: {prompt!r}. Compare visible pixels; do not assume success.",
            )
            summary = str(result.get("summary") or "")
            match = re.search(r"\{[^{}]+\}", summary, re.S)
            if not result.get("available") or not match:
                passed = similarity >= threshold
                return {
                    "supported": False, "pass": passed, "score": round(similarity * 10, 2),
                    "reason": "vision evaluator unavailable; similarity verified" if passed else f"similarity too low ({similarity:.2f})",
                    "similarity": round(similarity, 4),
                }
            parsed = json.loads(match.group(0))
            identity = parsed.get("identity_preserved") is True
            face = parsed.get("face_preserved") is True
            costume = parsed.get("costume_preserved") is True
            style_ok = parsed.get("style_preserved") is True
            changed = parsed.get("requested_change_applied") is True
            try:
                people = int(parsed.get("person_count", -1))
            except (TypeError, ValueError):
                people = -1
            reasons = []
            if similarity < threshold:
                reasons.append(f"similarity too low ({similarity:.2f})")
            if not identity or not face:
                reasons.append("identity/face not preserved")
            if not costume or not style_ok:
                reasons.append("costume/style not preserved")
            if not changed:
                reasons.append("requested change missing")
            if people != 1:
                reasons.append(f"person_count={people}")
            score = round(similarity * 5, 2) + sum((identity, face, costume, style_ok, changed)) + (2 if people == 1 else 0)
            return {
                "supported": True, "pass": not reasons, "score": score,
                "reason": "; ".join(reasons) if reasons else "pass", "similarity": round(similarity, 4),
                "identity_preserved": identity, "face_preserved": face, "costume_preserved": costume,
                "style_preserved": style_ok, "requested_change_applied": changed, "person_count": people,
            }
        except Exception as exc:
            passed = similarity >= threshold
            return {
                "supported": False, "pass": passed, "score": round(similarity * 10, 2),
                "reason": f"vision evaluator error: {exc}; similarity={'pass' if passed else 'fail'}",
                "similarity": round(similarity, 4),
            }
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @classmethod
    def _quality_rank(cls, source: Image.Image, output: Image.Image, style: str) -> float:
        return cls._similarity(source, output) - (1.0 if style == "photo" and cls._looks_cartoon(output) else 0.0)

    @staticmethod
    def _check_cancel(cancel_event) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("AI image job cancelled")

    @staticmethod
    def _attach_cancel_callback(pipe, kwargs: dict, steps: int, cancel_event, progress) -> None:
        if "callback_on_step_end" not in inspect.signature(pipe.__call__).parameters:
            return
        def callback(_pipe, step_index, _timestep, callback_kwargs):
            LocalImageService._check_cancel(cancel_event)
            if progress:
                current = min(steps, step_index + 1)
                progress(min(95, 35 + int(current / max(1, steps) * 60)), "Generating AI image", f"Step {current}/{steps}")
            return callback_kwargs
        kwargs["callback_on_step_end"] = callback

    def _runtime(self):
        try:
            import torch
        except ImportError as exc:
            raise ValueError("Local AI is not installed. Run SETUP_FREE_AI.bat.") from exc
        if not torch.cuda.is_available():
            raise RuntimeError("tao_anh_ai requires CUDA; refusing silent CPU fallback")
        # A real allocation catches stale/unsupported CUDA kernels, not just availability.
        probe = torch.ones(1, device="cuda") + 1
        torch.cuda.synchronize()
        del probe
        return torch, "cuda", torch.float16

    def _model_is_cached(self, model_id: str) -> bool:
        cache_name = "models--" + model_id.replace("/", "--")
        snapshots = self.model_dir / cache_name / "snapshots"
        return snapshots.is_dir() and any((item / "model_index.json").is_file() for item in snapshots.iterdir())

    def _select_model(self, kind: str, style: str, prompt: str, *, backend: str = "auto") -> str:
        forced = {"sdxl": SDXL_MODEL, "dreamshaper": DREAMSHAPER_MODEL, "sd15": self.model_id,
                  "flux": FLUX_MODEL, "flux-schnell": FLUX_SCHNELL_MODEL}
        if backend != "auto":
            model = forced.get(backend)
            if model is None:
                raise ValueError(f"Unsupported image backend: {backend}")
            if model != self.model_id and not self._model_is_cached(model):
                raise RuntimeError(f"Requested image backend is not cached: {model}")
            return model
        # FLUX.1 dev — best quality for text-to-image when available (12B MMDiT)
        if kind == "text" and self._model_is_cached(FLUX_MODEL):
            return FLUX_MODEL
        if kind == "text" and self._model_is_cached(FLUX_SCHNELL_MODEL):
            return FLUX_SCHNELL_MODEL
        if kind == "text" and self._model_is_cached(SDXL_MODEL):
            return SDXL_MODEL
        if kind in {"image", "inpaint"} and self._model_is_cached(DREAMSHAPER_MODEL):
            return DREAMSHAPER_MODEL
        # FLUX img2img/inpaint is supported via AutoPipeline, but SDXL ecosystem
        # is more battle-tested for edits; fall through to DreamShaper/SDXL.
        if kind in {"image", "inpaint"} and self._model_is_cached(FLUX_MODEL):
            return FLUX_MODEL
        return self.model_id

    @staticmethod
    def _generation_dimensions(size: str, model_id: str) -> tuple[int, int]:
        width, height = generation_dimensions(size)
        if model_id in FLUX_MODELS:
            # FLUX native: 1024x1024, or 1024x768 / 768x1024; must be multiple of 64
            if width == height:
                return 1024, 1024
            return (1024, 768) if width > height else (768, 1024)
        if model_id == SDXL_MODEL:
            if width == height:
                return 1024, 1024
            return (1152, 768) if width > height else (768, 1152)
        if model_id == DREAMSHAPER_MODEL and width == height:
            return 768, 768
        return width, height

    def _release_pipelines_except(self, keep_attr: str, model_id: str, torch_module) -> None:
        released = False
        for attr in ("_text_pipe", "_img_pipe", "_inpaint_pipe"):
            if attr != keep_attr or self._active_model != model_id:
                released = released or getattr(self, attr) is not None
                setattr(self, attr, None)
        gc.collect()
        # Empty the allocator only after real pipeline references were released.
        if released:
            torch_module.cuda.empty_cache()
        self._active_model = None

    def _load_pipeline(self, kind: str, model_id: str | None = None):
        attr = {"text": "_text_pipe", "image": "_img_pipe", "inpaint": "_inpaint_pipe"}[kind]
        model_id = model_id or self.model_id
        if getattr(self, attr) is not None and self._active_model is None:
            return getattr(self, attr)  # explicitly injected test pipeline
        if getattr(self, attr) is not None and self._active_model == model_id:
            return getattr(self, attr)
        with self._lock:
            if getattr(self, attr) is not None and self._active_model == model_id:
                return getattr(self, attr)
            try:
                from diffusers import AutoPipelineForImage2Image, AutoPipelineForInpainting, AutoPipelineForText2Image
            except ImportError as exc:
                raise ValueError("Diffusers is not installed. Run SETUP_FREE_AI.bat.") from exc
            cls = {"text": AutoPipelineForText2Image, "image": AutoPipelineForImage2Image, "inpaint": AutoPipelineForInpainting}[kind]
            torch_module, device, dtype = self._runtime()
            self._release_pipelines_except(attr, model_id, torch_module)
            # FLUX uses bfloat16; all others use float16
            if model_id in FLUX_MODELS:
                load_kwargs = dict(
                    torch_dtype=torch_module.bfloat16,
                    cache_dir=str(self.model_dir),
                    local_files_only=True,
                )
            else:
                load_kwargs = dict(torch_dtype=dtype, cache_dir=str(self.model_dir), local_files_only=True)
                if model_id == DREAMSHAPER_MODEL:
                    load_kwargs["variant"] = "fp16"
                if model_id != SDXL_MODEL:
                    load_kwargs.update(safety_checker=None, requires_safety_checker=False)
            pipe = cls.from_pretrained(model_id, **load_kwargs)
            # FLUX benefits from CPU offload on 16 GB VRAM (12B model)
            if model_id in FLUX_MODELS:
                try:
                    pipe.enable_model_cpu_offload()
                except Exception:
                    pipe.to(device)
            else:
                pipe.to(device)
            setattr(self, attr, pipe)
            self._active_model = model_id
            return pipe

    def _text_pipeline(self, model_id: str | None = None): return self._load_pipeline("text", model_id)
    def _image_pipeline(self, model_id: str | None = None): return self._load_pipeline("image", model_id)
    def _inpaint_pipeline(self, model_id: str | None = None): return self._load_pipeline("inpaint", model_id)
