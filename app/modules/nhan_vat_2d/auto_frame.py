from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# Same foreground/background split already used and validated by
# single_character_quality.py and compact_composition.py for these exact
# plain-gray-background renders - kept identical here so the bbox this module
# measures matches what the gate itself will measure afterward.
_BG_DIST_THRESHOLD = 34.0

# Targets sit inside compact_composition.py's accepted window (height_ratio
# in [0.52, 0.90], width_ratio in [0.20, 0.72]), but deliberately close to the
# upper end rather than the middle of that range. face_quality.py and
# fullbody_quality.py crop FIXED fractional bands of the canvas (e.g. face =
# top 5%-38% of height) that were calibrated against renders where the
# character fills most of the frame - zooming out to a "nicer-looking" middle
# ratio (~0.70) empirically pushed the real face/feet pixels outside those
# fixed bands and broke those checks (real test evidence, see
# MODULE_STATUS.md - offline sweep across 31 real historical candidates:
# 0.83 left 2 borderline face-score regressions; 0.86 gave 0 regressions
# while still flipping 8/10 framed candidates to a compact_composition pass).
_TARGET_HEIGHT_RATIO = 0.86
# Deliberately close to the hard gate cap (0.72), not a "nicer" middle value:
# many of these renders sit on a circular pedestal/base that is wider than
# the character itself, which inflates bbox width for reasons unrelated to
# pose. A tighter width target would treat that as "needs more zoom-out" and
# fight the height target, re-breaking face_quality's fixed-fraction crop
# (real test evidence). This way width only intervenes to stop an outright
# compact_composition width failure, while height stays the primary driver
# for the common case.
_TARGET_WIDTH_RATIO = 0.62
_MIN_HEIGHT_RATIO_FLOOR = 0.75

# Extra slack around the raw detected bbox so thin extremities (hair wisps,
# a blade tip, a small accessory) sitting near the detection threshold are
# never clipped by the safety-margin math below.
_SAFETY_MARGIN_FRAC = 0.02
_MIN_FOREGROUND_PIXELS = 200
# If the detected bbox touches (within this many pixels of) BOTH edges of an
# axis, its true extent on that axis is unknown - it may continue past the
# canvas boundary, or the "foreground" reaching the edge may itself be a
# lighting vignette rather than real content. Either way it can't be safely
# targeted - see _foreground_bbox.
_EDGE_TOUCH_TOLERANCE_PX = 3


def _load_rgb(source) -> Image.Image:
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGB")
    if isinstance(source, (str, Path)):
        return Image.open(source).convert("RGB")
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    raise TypeError("Unsupported image source")


def _detect_background_color(arr: np.ndarray) -> np.ndarray:
    h, w, _ = arr.shape
    patch = max(8, min(h, w) // 20)
    corners = np.concatenate([
        arr[:patch, :patch].reshape(-1, 3), arr[:patch, -patch:].reshape(-1, 3),
        arr[-patch:, :patch].reshape(-1, 3), arr[-patch:, -patch:].reshape(-1, 3),
    ], axis=0)
    return np.median(corners, axis=0)


def _foreground_bbox(im: Image.Image, bg: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight bounding box of every foreground pixel, using the exact same
    global color-distance threshold compact_composition.py itself uses (no
    stricter filtering) - this bbox is deliberately treated as a lower bound
    on what the gate will measure downstream, so the crop math below always
    protects at least this much and the gate's own re-measurement of the
    output can never come out larger than intended.

    An earlier version restricted this to the connected component touching
    the image center, meant to reject background vignettes/shadows that
    happen to cross the threshold far from the character. Real test evidence
    showed that approach could itself UNDER-count real content (a low-
    contrast ribbon accessory, a pedestal edge softened by anti-aliasing) by
    treating it as "disconnected", producing a bbox smaller than what
    compact_composition.py would later measure on the very same pixels -
    i.e. a crop that could come closer to real content than intended. Using
    the plain, unrestricted threshold here instead guarantees the protected
    region is always a superset of anything the gate itself would call
    foreground, at the cost of sometimes being unable to tighten the frame
    much when the background itself isn't clean (see the edge-touch check
    below, which is the actual safety valve for that case).

    A light binary opening (erode then dilate) still removes isolated
    single-pixel sensor/compression noise without eating real thin
    extremities, which stay several pixels wide at native ~1024px
    resolution.
    """
    arr = np.asarray(im, dtype=np.float32)
    dist = np.linalg.norm(arr - bg[None, None, :], axis=2)
    raw_mask = (dist > _BG_DIST_THRESHOLD).astype(np.uint8) * 255
    mask_img = Image.fromarray(raw_mask, mode="L")
    opened = mask_img.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    mask = np.asarray(opened) > 0
    ys, xs = np.where(mask)
    if len(xs) < _MIN_FOREGROUND_PIXELS:
        return None

    h, w = mask.shape
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    tol = _EDGE_TOUCH_TOLERANCE_PX
    x_spans_canvas = x0 <= tol and x1 >= w - 1 - tol
    y_spans_canvas = y0 <= tol and y1 >= h - 1 - tol
    if x_spans_canvas or y_spans_canvas:
        # The detected extent touches both edges of an axis: its true size on
        # that axis is unknowable (could be a lighting vignette with no real
        # edge, or genuine content already cut off by the canvas). Either way
        # there is no reliable target to frame to - skip, matching every
        # other inconclusive-detection case (real test evidence: a soft
        # ambient vignette measured corner-to-edge distance up to 58 against
        # this 34 threshold, making the entire canvas register as
        # foreground).
        return None
    return x0, y0, x1, y1


def auto_frame_character(source) -> bytes | None:
    """Deterministic post-process run right after generation, before any
    quality gate: crop away excess plain background and/or pad with the
    detected background color so the character lands inside
    compact_composition.py's accepted height/width-ratio window.

    Only ever touches canvas framing - never the character's own pixels
    (face/body/pose/clothes/weapon/colors/style are byte-identical inside the
    kept region, modulo the final uniform LANCZOS resize back to the original
    canvas size, which scales everything equally and distorts nothing since
    the frame is built to preserve the original aspect ratio).

    A crop is only ever applied to background border pixels that sit strictly
    outside the (safety-margin-padded) character bounding box; whenever the
    target composition would require cutting closer than that box, this pads
    with background color instead of cropping, so hair/feet/weapon/accessories
    are never clipped.

    Returns None (caller must keep the original image untouched) if detection
    is inconclusive or any invariant can't be confirmed - this function must
    never crash the generation pipeline and must never risk cropping into the
    character.
    """
    try:
        im = _load_rgb(source)
        w, h = im.size
        bg = _detect_background_color(np.asarray(im, dtype=np.float32))
        bbox = _foreground_bbox(im, bg)
        if bbox is None:
            return None
        x0, y0, x1, y1 = bbox
        pad_px = max(4, int(_SAFETY_MARGIN_FRAC * min(w, h)))
        x0 = max(0, x0 - pad_px)
        y0 = max(0, y0 - pad_px)
        x1 = min(w - 1, x1 + pad_px)
        y1 = min(h - 1, y1 + pad_px)
        bbox_w = x1 - x0 + 1
        bbox_h = y1 - y0 + 1
        if bbox_w <= 0 or bbox_h <= 0:
            return None
        cx = (x0 + x1 + 1) / 2.0
        cy = (y0 + y1 + 1) / 2.0

        # The frame preserves the original canvas aspect ratio (w/h) so the
        # final resize back to (w, h) is a uniform scale only - it never
        # stretches or squashes the character's proportions.
        frame_h_for_height = bbox_h / _TARGET_HEIGHT_RATIO
        frame_w_for_width = bbox_w / _TARGET_WIDTH_RATIO
        frame_h_for_width = frame_w_for_width * (h / w)
        frame_h = max(frame_h_for_height, frame_h_for_width, bbox_h * 1.05, bbox_w * 1.05 * (h / w))
        if bbox_h / frame_h < _MIN_HEIGHT_RATIO_FLOOR:
            # An extreme sideways prop (e.g. a weapon swung far out) is
            # demanding an oversized frame - don't zoom the character out to
            # near-illegible size just to chase the width target.
            frame_h = bbox_h / _MIN_HEIGHT_RATIO_FLOOR
        frame_w = frame_h * (w / h)

        frame_left = cx - frame_w / 2.0
        frame_top = cy - frame_h / 2.0
        frame_right = frame_left + frame_w
        frame_bottom = frame_top + frame_h

        pad_left = max(0, int(np.ceil(-frame_left)))
        pad_top = max(0, int(np.ceil(-frame_top)))
        pad_right = max(0, int(np.ceil(frame_right - w)))
        pad_bottom = max(0, int(np.ceil(frame_bottom - h)))

        bg_color = tuple(int(round(c)) for c in bg)
        canvas = Image.new("RGB", (w + pad_left + pad_right, h + pad_top + pad_bottom), bg_color)
        canvas.paste(im, (pad_left, pad_top))

        crop_left = int(round(frame_left + pad_left))
        crop_top = int(round(frame_top + pad_top))
        crop_right = crop_left + int(round(frame_w))
        crop_bottom = crop_top + int(round(frame_h))

        # Defensive containment check: the safety-padded bbox (translated into
        # the padded canvas' coordinate space) must be fully inside the crop
        # box. Should always hold by construction; if it doesn't, bail out to
        # the original image rather than risk clipping the character.
        bbox_left_c, bbox_top_c = x0 + pad_left, y0 + pad_top
        bbox_right_c, bbox_bottom_c = x1 + 1 + pad_left, y1 + 1 + pad_top
        if not (crop_left <= bbox_left_c and crop_top <= bbox_top_c
                and crop_right >= bbox_right_c and crop_bottom >= bbox_bottom_c):
            return None

        framed = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))
        if framed.size != (w, h):
            framed = framed.resize((w, h), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        framed.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None
