"""Shared prompt contract for AI Video Factory generation modules.

One user instruction is kept as the source of truth.  Renderers may have very
 different text encoders (CLIP, T5, or no text conditioning at all), so this
module separates the prompt into priority layers instead of pretending every
backend can consume an arbitrarily long string.

Priority order:
    1. USER CORE      - subject/count/action/required objects/layout
    2. COMPOSITION    - framing/camera/pose/environment constraints
    3. QUALITY/STYLE  - polish terms and generic quality hints

CLIP-backed pipelines are fitted to their *real tokenizer limit* at call time.
When something must be dropped, the tail (quality/style) is dropped first;
the user core stays at the front.  This prevents the old failure mode where
"holding a sword" or another required object sat after generic quality prose
and was silently truncated at 77 tokens.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import unicodedata
from typing import Iterable, Any

PROMPT_CONTRACT_VERSION = "1.2"

# Bilingual high-value terms. Matching is accent-insensitive, output is not.
_HIGH_VALUE = {
    # counts / identity
    "one", "single", "exactly", "1", "two", "2", "three", "3", "four", "4",
    "mot", "hai", "ba", "bon",
    "female", "woman", "girl", "male", "man", "boy", "adult", "baby", "child", "kid", "young", "old", "elderly", "nu", "nam",
    "character", "hero", "heroine", "warrior", "swordsman", "swordswoman", "archer",
    "samurai", "wuxia", "knight", "nhan", "vat", "kiem", "si", "cung", "thu", "meo", "cho", "chim", "ngua", "xe", "tau", "thuyen",
    # required objects / actions / entities
    "hold", "holding", "holds", "carry", "carrying", "wear", "wearing", "use", "using", "ride", "riding", "drive", "driving", "fly", "flying",
    "cam", "mac", "lai", "bay", "di", "sword", "blade", "katana", "bow", "axe", "spear", "staff", "shield",
    "gun", "rifle", "hammer", "weapon", "armor", "armour", "robe", "costume", "outfit",
    "hair", "cape", "cloak", "sash", "belt", "boots", "helmet", "hat", "shirt", "dress", "coat", "pants", "shoes",
    "cat", "dog", "bird", "horse", "wolf", "tiger", "lion", "fish", "dragon",
    "car", "truck", "bus", "motorcycle", "bike", "bicycle", "boat", "ship", "train", "airplane", "plane", "helicopter",
    "robot", "machine", "engine", "gear", "aircraft", "oto", "robot",
    # framing / layout
    "full", "body", "feet", "front", "side", "profile", "centered", "top-down", "isometric",
    "toan", "than", "chinh", "dien", "nghieng",
    # environment / map / weather / time / colors
    "map", "terrain", "world", "road", "river", "lake", "coast", "coastline", "mountain",
    "cliff", "forest", "desert", "snow", "volcano", "village", "city", "castle", "bridge", "street", "room", "factory", "beach", "ocean", "sea", "sky",
    "ban", "do", "dia", "hinh", "duong", "song", "ho", "bien", "nui", "rung", "sa", "mac", "lang", "thanh", "cau",
    "rain", "rainy", "sunny", "cloudy", "storm", "fog", "night", "day", "sunset", "sunrise", "moon", "sun",
    "mua", "nang", "may", "bao", "suong", "dem", "ngay", "mat", "troi", "trang",
    "red", "blue", "green", "yellow", "black", "white", "silver", "gold", "brown", "pink", "purple", "orange",
    "do", "xanh", "vang", "den", "trang", "bac", "nau", "hong", "tim", "cam",
    # style words can matter, but rank below subject/action in clause scoring
    "photorealistic", "realistic", "anime", "cartoon", "cinematic", "fantasy", "pixel",
}

_CRITICAL_VALUE = {
    "one", "single", "exactly", "1", "two", "2", "three", "3", "four", "4", "mot", "hai", "ba", "bon",
    "female", "woman", "girl", "male", "man", "boy", "baby", "child", "kid", "young", "old", "elderly", "nu", "nam", "character", "hero", "heroine", "warrior",
    "swordsman", "swordswoman", "archer", "samurai", "wuxia", "nhan", "vat", "hold", "holding", "holds", "carry",
    "carrying", "wear", "wearing", "ride", "riding", "drive", "driving", "fly", "flying", "cam", "mac", "lai", "bay",
    "sword", "blade", "katana", "bow", "axe", "spear", "staff", "shield", "gun", "rifle", "hammer", "weapon",
    "armor", "armour", "robe", "costume", "outfit", "hair", "cape", "cloak", "sash", "belt", "boots", "helmet", "hat",
    "shirt", "dress", "coat", "pants", "shoes", "cat", "dog", "bird", "horse", "dragon", "robot", "machine", "engine", "gear",
    "car", "truck", "bus", "motorcycle", "bike", "bicycle", "boat", "ship", "train", "airplane", "plane", "helicopter", "xe", "oto", "tau", "thuyen",
    "full", "body", "feet", "front", "side", "profile", "centered", "top-down", "isometric", "toan", "than",
    "road", "river", "lake", "coast", "coastline", "mountain", "cliff", "forest", "desert", "snow", "volcano", "village", "city", "castle", "bridge", "street", "room", "factory", "beach", "ocean", "sea", "sky",
    "map", "terrain", "world", "ban", "do", "dia", "hinh", "duong", "song", "ho", "bien", "nui", "rung", "sa", "mac", "lang", "thanh", "cau",
    "rain", "rainy", "sunny", "cloudy", "storm", "fog", "night", "day", "sunset", "sunrise", "moon", "sun", "mua", "nang", "may", "bao", "suong", "dem", "ngay",
    "red", "blue", "green", "yellow", "black", "white", "silver", "gold", "brown", "pink", "purple", "orange", "do", "xanh", "vang", "den", "trang", "bac", "nau", "hong", "tim", "cam",
}

_ACTION_OBJECT_RE = re.compile(
    r"\b(?:hold(?:ing|s)?|carry(?:ing|ies)?|use(?:s|ing)?|wear(?:s|ing)?|ride|riding|drive|driving|fly|flying|run(?:ning)?|sit(?:ting)?|stand(?:ing)?|cam|mac|lai|bay|di|"
    r"sword|blade|katana|bow|axe|spear|staff|shield|gun|rifle|hammer|weapon|helmet|hat|shirt|dress|coat|pants|shoes|"
    r"car|truck|bus|motorcycle|bike|bicycle|boat|ship|train|airplane|plane|helicopter|robot|machine|engine|gear|cat|dog|bird|horse|dragon|kiem|cung|xe|oto|tau|thuyen|meo|cho|chim|ngua)\b",
    re.I,
)
_COUNT_ID_RE = re.compile(
    r"\b(?:one|single|exactly|1|two|2|three|3|four|4|mot|hai|ba|bon|female|woman|girl|male|man|boy|"
    r"baby|child|kid|young|old|elderly|nu|nam|character|hero|heroine|warrior|swordsman|swordswoman|archer|samurai|wuxia|"
    r"cat|dog|bird|horse|dragon|robot|car|truck|bus|motorcycle|bike|bicycle|boat|ship|train|airplane|plane|helicopter|nhan\s+vat|meo|cho|chim|ngua|xe|oto|tau|thuyen)\b",
    re.I,
)
_LAYOUT_RE = re.compile(
    r"\b(?:full\s+body|top[- ]down|isometric|front|profile|centered|toan\s+than|road|river|lake|coast|mountain|forest|desert|snow|volcano|"
    r"village|city|castle|bridge|street|room|factory|beach|ocean|sea|sky|night|day|sunset|sunrise|moon|sun|rain|rainy|sunny|cloudy|storm|fog|"
    r"duong|song|ho|bien|nui|rung|lang|thanh|cau|dem|ngay|mua|nang|may|bao|suong)\b",
    re.I,
)


def _ascii(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).lower()


def _clean(text: str) -> str:
    text = re.sub(r"[\r\n\t]+", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip(" ,.;")


def _trim_important_words(text: str, max_words: int) -> str:
    """Trim one long clause while retaining windows around important words."""
    words = _clean(text).split()
    if len(words) <= max_words:
        return " ".join(words)
    normalized = [re.sub(r"[^a-z0-9_-]", "", _ascii(w)) for w in words]
    critical: set[int] = set()
    for i, word in enumerate(normalized):
        if word in _CRITICAL_VALUE:
            critical.update(range(max(0, i - 3), min(len(words), i + 5)))

    # Critical windows win over generic prose even when they appear at the end.
    # Then use a small beginning window for context, then fill remaining gaps.
    preferred = list(sorted(critical))
    head = list(range(min(8, len(words))))
    selected: list[int] = []
    for idx in preferred + head:
        if idx not in selected:
            selected.append(idx)
        if len(selected) >= max_words:
            break
    if len(selected) < max_words:
        for i in range(len(words)):
            if i not in selected:
                selected.append(i)
                if len(selected) >= max_words:
                    break
    return " ".join(words[i] for i in selected[:max_words])


def compact_core_requirements(text: str, max_words: int = 34) -> str:
    """Keep the user's semantically mandatory clauses before cosmetic prose.

    This is deterministic and does not invent attributes. It works with both
    Vietnamese and English prompts and intentionally preserves literal text.
    """
    text = _clean(text)
    if not text:
        return ""
    if len(text.split()) <= max_words:
        return text

    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+|[;,]+", text) if c.strip()]
    if len(clauses) <= 1:
        return _trim_important_words(text, max_words)

    scored: list[tuple[int, int, str]] = []
    for idx, clause in enumerate(clauses):
        plain = _ascii(clause)
        score = 0
        if _COUNT_ID_RE.search(plain):
            score += 5
        if _ACTION_OBJECT_RE.search(plain):
            score += 5
        if _LAYOUT_RE.search(plain):
            score += 3
        if any(word in plain for word in ("photoreal", "realistic", "anime", "cinematic", "fantasy", "pixel")):
            score += 1
        if idx == 0:
            score += 1
        scored.append((score, idx, clause))

    # Select by importance, then restore original order for readability.
    picked: list[tuple[int, str]] = []
    used = 0
    for score, idx, clause in sorted(scored, key=lambda x: (-x[0], x[1])):
        if score <= 0 and picked:
            continue
        remaining = max_words - used
        if remaining <= 0:
            break
        value = _trim_important_words(clause, remaining)
        count = len(value.split())
        if value and count:
            picked.append((idx, value))
            used += count
    if not picked:
        return _trim_important_words(text, max_words)
    return ", ".join(value for _idx, value in sorted(picked, key=lambda x: x[0]))


def _append_with_word_budget(parts: list[str], clause: str, max_words: int) -> None:
    clause = _clean(clause)
    if not clause:
        return
    used = sum(len(p.split()) for p in parts)
    remaining = max_words - used
    if remaining <= 0:
        return
    words = clause.split()
    if len(words) <= remaining:
        parts.append(clause)
    elif remaining >= 4:
        parts.append(" ".join(words[:remaining]))


def build_priority_prompt(
    user_prompt: str,
    *,
    mandatory: Iterable[str] = (),
    composition: Iterable[str] = (),
    quality: Iterable[str] = (),
    max_words: int = 64,
    core_max_words: int = 34,
    core_label: str = "USER REQUIREMENT",
) -> str:
    """Compile a three-layer prompt with the user core always first."""
    core = compact_core_requirements(user_prompt, max_words=min(core_max_words, max_words))
    parts: list[str] = []
    if core:
        _append_with_word_budget(parts, f"{core_label}: {core}", max_words)
    for clause in mandatory:
        _append_with_word_budget(parts, clause, max_words)
    for clause in composition:
        _append_with_word_budget(parts, clause, max_words)
    for clause in quality:
        _append_with_word_budget(parts, clause, max_words)
    return ". ".join(p.strip(" .") for p in parts if p.strip())


def build_video_prompt(user_prompt: str, *, extra: Iterable[str] = (), max_words: int = 180) -> str:
    """Long-context variant for text-conditioned video models (e.g. T5)."""
    return build_priority_prompt(
        user_prompt,
        mandatory=extra,
        max_words=max_words,
        core_max_words=min(140, max_words),
        core_label="SUBJECT/STORY",
    )


@dataclass(frozen=True)
class TokenFit:
    text: str
    token_count: int | None
    token_limit: int | None
    truncated: bool
    tokenizer_count: int

    def as_dict(self) -> dict:
        return asdict(self)


def _usable_tokenizers(pipe: Any) -> list[Any]:
    out = []
    for name in ("tokenizer", "tokenizer_2"):
        tok = getattr(pipe, name, None)
        if tok is None or not callable(tok):
            continue
        limit = getattr(tok, "model_max_length", None)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            continue
        # Some tokenizers use huge sentinel max lengths. Those are not useful
        # for a real hard-context guard.
        if 4 <= limit <= 4096:
            out.append(tok)
    return out


def _count_tokens(tokenizer: Any, text: str) -> int:
    # `verbose=False` prevents Transformers from printing the scary
    # "sequence length ... > 77" warning while we are *measuring* the
    # untruncated candidate. Older/custom tokenizers may not accept it.
    try:
        encoded = tokenizer(text, truncation=False, add_special_tokens=True, verbose=False)
    except TypeError:
        encoded = tokenizer(text, truncation=False, add_special_tokens=True)
    ids = getattr(encoded, "input_ids", None)
    if ids is None and isinstance(encoded, dict):
        ids = encoded.get("input_ids")
    if ids is None:
        return 0
    if ids and isinstance(ids[0], (list, tuple)):
        ids = ids[0]
    return len(ids)


def fit_prompt_to_pipeline(text: str, pipe: Any) -> TokenFit:
    """Fit a priority-ordered prompt to the actual text encoders on a pipeline.

    Tail trimming is deliberate: callers must put USER CORE first.  The
    function checks both SDXL tokenizers when present and therefore prevents
    the transformers 78>77 warning instead of merely counting whitespace.
    """
    text = _clean(text)
    tokenizers = _usable_tokenizers(pipe)
    if not tokenizers:
        return TokenFit(text=text, token_count=None, token_limit=None, truncated=False, tokenizer_count=0)

    limits = [int(tok.model_max_length) for tok in tokenizers]
    limit = min(limits)
    # A prompt that measures exactly model_max_length is valid — CLIP encodes
    # BOS+EOS inside that budget already.  The old "safe margin of 2" was
    # *causing* truncation: a 74-token prompt against limit=75 (75-2=73)
    # got pointlessly trimmed, losing critical weapon/background/composition
    # clauses at the tail.  Only truncate when the count truly exceeds the
    # hard limit.  If a particular backend warns at exactly N, that warning
    # is cosmetic and does not affect output quality.
    safe_limits = [max(4, value) for value in limits]
    safe_limit = min(safe_limits)

    def counts(value: str) -> list[int]:
        return [_count_tokens(tok, value) for tok in tokenizers]

    initial = counts(text)
    if all(c <= allowed for c, allowed in zip(initial, safe_limits)):
        return TokenFit(text=text, token_count=max(initial), token_limit=safe_limit, truncated=False, tokenizer_count=len(tokenizers))

    words = text.split()
    lo, hi = 1, len(words)
    best = words[0] if words else ""
    best_count = max(counts(best)) if best else 0
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = " ".join(words[:mid])
        cts = counts(candidate)
        ok = all(c <= allowed for c, allowed in zip(cts, safe_limits))
        if ok:
            best = candidate
            best_count = max(cts)
            lo = mid + 1
        else:
            hi = mid - 1
    return TokenFit(text=best, token_count=best_count, token_limit=safe_limit, truncated=(best != text), tokenizer_count=len(tokenizers))


def prompt_contract_meta(*, module: str, fit: TokenFit | None = None, source_words: int | None = None) -> dict:
    result = {"version": PROMPT_CONTRACT_VERSION, "module": module}
    if source_words is not None:
        result["source_words"] = int(source_words)
    if fit is not None:
        result.update(fit.as_dict())
        result.pop("text", None)
    return result
