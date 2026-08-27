"""Render styled text to transparent PNG for FFmpeg overlay composition."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

_FONT_CANDIDATES = {
    "segoe": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf"],
    "arial": ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"],
    "impact": ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "georgia": ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf"],
}


def _font(size: int, family: str = "segoe"):
    candidates = _FONT_CANDIDATES.get(family, _FONT_CANDIDATES["segoe"]) + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for raw in candidates:
        path = Path(raw)
        if path.is_file():
            return ImageFont.truetype(str(path), size=max(8, size))
    try:
        return ImageFont.load_default(size=max(8, size))
    except TypeError:
        return ImageFont.load_default()


def _rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    try:
        rgb = ImageColor.getrgb(value or "#ffffff")
    except ValueError:
        rgb = (255, 255, 255)
    return (rgb[0], rgb[1], rgb[2], alpha)


def render_text_png(text: str, output: str | Path, font_size: int, color: str = "#ffffff", outline_color: str = "#000000", outline_width: int = 3, background: str = "#000000", background_opacity: float = 0.0, padding: int = 18, font_family: str = "segoe", shadow_color: str = "#000000", shadow_opacity: float = 0.0, shadow_blur: int = 0) -> Path:
    clean = (text or "").strip() or "Text"
    font = _font(font_size, font_family)
    stroke = max(0, int(outline_width))
    shadow_blur = max(0, min(30, int(shadow_blur)))
    extra = max(8, shadow_blur * 3)
    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    box = draw.multiline_textbbox((0, 0), clean, font=font, stroke_width=stroke, spacing=6, align="center")
    width = max(4, box[2] - box[0] + padding * 2 + extra * 2)
    height = max(4, box[3] - box[1] + padding * 2 + extra * 2)
    bg_alpha = max(0, min(255, int(float(background_opacity) * 255)))
    image = Image.new("RGBA", (width, height), _rgba(background, bg_alpha))
    center = (width / 2, padding + extra - box[1])
    if shadow_opacity > 0:
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.multiline_text((center[0]+2, center[1]+3), clean, font=font, fill=_rgba(shadow_color, int(255*max(0,min(1,shadow_opacity)))), anchor="ma", align="center", spacing=6, stroke_width=stroke, stroke_fill=_rgba(outline_color, 180))
        if shadow_blur:
            shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
        image.alpha_composite(shadow)
    draw = ImageDraw.Draw(image)
    draw.multiline_text(center, clean, font=font, fill=_rgba(color), anchor="ma", align="center", spacing=6, stroke_width=stroke, stroke_fill=_rgba(outline_color))
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "PNG")
    return target
