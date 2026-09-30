"""Auto Producer — Linear pipeline for AI Video Director.

Architecture: SIMPLE / STABLE / FAST — KHÔNG CHẤP VÁ.

Pipeline per scene:
    prepare_reference() → generate_image() → validate_image() → generate_video() → finalize_scene()

Rules:
    - MAX_IMAGE_ATTEMPTS = 2, no nested retries
    - Face/anatomy gate runs ONCE (in validate_image), NOT again before SVD
    - Multi-panel check runs ONCE (in validate_image)
    - Video generation has NO retry loop — if SVD output fails QA, the scene fails
    - Atomic file output: write to .tmp, rename to final on success
    - Human/non-human subject separation (YuNet/SFace only for human)
    - FAST MODE: IMAGE_STEPS = 14-16, max 2 candidates

DO NOT touch: UI, FFmpeg core, SVD core, Character 2D.
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageFilter, ImageStat, ImageChops

from .quality import image_quality, video_quality, parse_duration


class AutoProduceCancelled(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_IMAGE_ATTEMPTS = 2  # Hard cap: 1 image + tối đa 1 retry
FAST_STEPS_HIGH = 14    # FAST MODE steps for high/final quality
FAST_STEPS_NORMAL = 16 # FAST MODE steps for draft/balanced quality


class AutoProducer:
    """Linear pipeline orchestrator over independent AI Video Factory modules.

    The Director adds contracts: character anchor/lock, subject-aware anatomy
    gate, bounded image retry (max 1), and a high-quality final master.
    """

    def __init__(self, app, project_root: Path):
        self.app = app
        self.project_root = Path(project_root)
        self.project_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Small utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _call_compat(fn, *args, **kwargs):
        """Call a function, filtering kwargs to only those it accepts."""
        try:
            sig = inspect.signature(fn)
            accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        except Exception:
            accepted = kwargs
        return fn(*args, **accepted)

    @staticmethod
    def _ffmpeg() -> str:
        path = shutil.which("ffmpeg")
        if not path:
            raise RuntimeError("Không tìm thấy ffmpeg trong PATH")
        return path

    @staticmethod
    def _ratio_size(ratio: str, quality: str = "balanced") -> tuple[int, int]:
        final = quality in {"high", "final"}
        ratio = (ratio or "16:9").strip()
        if ratio == "9:16":
            return (1080, 1920) if final else (720, 1280)
        if ratio == "1:1":
            return (1440, 1440) if final else (1080, 1080)
        return (1920, 1080) if final else (1280, 720)

    @staticmethod
    def _image_size_for_ratio(ratio: str) -> str:
        if ratio == "9:16":
            return "1024x1536"
        if ratio == "1:1":
            return "1024x1024"
        return "1536x1024"

    @staticmethod
    def _style_for_plan(plan: dict) -> str:
        text = str((plan.get("concept") or {}).get("style") or "").lower()
        if any(x in text for x in ("anime", "manga")):
            return "anime"
        if any(x in text for x in ("fantasy", "tiên hiệp", "game", "xianxia")):
            return "fantasy"
        if any(x in text for x in ("illustration", "minh họa")):
            return "illustration"
        if any(x in text for x in ("3d", "cartoon")):
            return "cartoon3d"
        if any(x in text for x in ("cinematic", "điện ảnh")):
            return "cinematic"
        return "photo"

    @staticmethod
    def _image_steps(quality: str, fast_mode: bool = False) -> int | None:
        """Override diffusion steps. FAST MODE uses 14-16."""
        if fast_mode:
            return FAST_STEPS_HIGH if quality in {"high", "final"} else FAST_STEPS_NORMAL
        return None

    @staticmethod
    def _image_gen_quality(quality: str, fast_mode: bool = False) -> str:
        if fast_mode:
            return "balanced"
        return quality

    @staticmethod
    def _generator_quality(quality: str) -> str:
        return "high" if quality in {"high", "final"} else quality

    @staticmethod
    def _looks_character_based(plan: dict) -> bool:
        if not bool((plan.get("concept") or {}).get("character_lock", True)):
            return False
        text = " ".join([
            str((plan.get("concept") or {}).get("idea") or ""),
            *[str(s.get("visual") or "") for s in (plan.get("scenes") or [])[:4]],
        ]).lower()
        words = (
            "nhân vật", "cô gái", "cô ", "nữ ", "nam ", "anh ", "người ", "cung thủ", "kiếm sĩ",
            "character", "woman", "girl", "man", "boy", "archer", "warrior", "hero", "heroine",
        )
        return any(w in text for w in words)

    @staticmethod
    def _reference_lock_prompt(plan: dict) -> str:
        c = plan.get("concept") or {}
        locks = []
        if c.get("reference_lock_face", True):
            locks.append("face, eyes, facial proportions and identity")
        if c.get("reference_lock_body", True):
            locks.append("body proportions and silhouette")
        if c.get("reference_lock_costume", True):
            locks.append("hair, costume, colors, accessories and weapon design")
        if not locks:
            return ""
        return (
            " Reference image is the visual source of truth. Preserve " + "; preserve ".join(locks) + "."
            " Same exact face, symmetrical natural face, correct eyes, nose and mouth, no facial distortion, no duplicated facial features."
            " Single scene, single camera angle, one character only. "
            "No character sheet, no contact sheet, no model sheet, no turnaround, no multi-view, no lineup, no grid, no collage, no split screen."
            " Negative: deformed face, asymmetric eyes, warped face, duplicated face, malformed mouth, distorted nose, extra facial features."
        )

    def _anchor_prompt(self, plan: dict) -> str:
        c = plan.get("concept") or {}
        idea = str(c.get("idea") or plan.get("title") or "primary character")
        style = str(c.get("style") or "cinematic")
        return (
            f"Primary character identity reference for: {idea}. {style}. Exactly one main character, "
            "three-quarter full-body neutral hero pose, face clearly visible, symmetric eyes, natural mouth, "
            "correct anatomy, coherent hair, costume fully readable, clean simple background, sharp high detail. "
            "This image is the identity anchor; no duplicate person, no extra face, no deformed hands."
        )

    def _uploaded_reference_path(self, plan: dict) -> Path | None:
        c = plan.get("concept") or {}
        rid = str(c.get("character_reference_id") or "").strip()
        if not rid or not rid.isalnum() or len(rid) > 64:
            return None
        path = self.project_root.parent / "references" / f"{rid}.png"
        return path if path.is_file() else None

    @staticmethod
    def _tmp_path(dst: Path) -> Path:
        """Build a temp path that preserves the original extension.
        e.g. scene_01_final.mp4 → scene_01_final.tmp.mp4
        FFmpeg auto-detects format from the extension, so .mp4 must be last.
        Preview endpoint globs for *.mp4 and *.png — .tmp.mp4 is NOT matched.
        """
        return dst.parent / (dst.stem + ".tmp" + dst.suffix)

    @staticmethod
    def _atomic_write(src: Path, dst: Path):
        """Atomically write src → dst: copy to .tmp.ext, then rename."""
        tmp = AutoProducer._tmp_path(dst)
        shutil.copy2(src, tmp)
        tmp.replace(dst)

    @staticmethod
    def _atomic_copy(src: Path, dst: Path):
        """Atomically copy src → dst: copy to .tmp.ext, then rename."""
        tmp = AutoProducer._tmp_path(dst)
        shutil.copy2(src, tmp)
        tmp.replace(dst)

    # ------------------------------------------------------------------
    # Multi-panel detector (single use, in validate_image only)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_multi_panel_image(path: Path) -> tuple[bool, str]:
        """Detect character sheets, contact sheets, grids, multi-view montages."""
        try:
            with Image.open(path) as im:
                im.load()
                w, h = im.size
                if w > h * 2.2:
                    return True, f"aspect_ratio={w}:{h} (too wide, likely multi-panel)"
                sample = im.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
                pixels = list(sample.getdata())
                light_bg = sum(
                    1 for r, g, b in pixels
                    if min(r, g, b) > 220 and max(r, g, b) - min(r, g, b) < 25
                ) / max(1, len(pixels))
                px = sample.load()
                w_s, h_s = sample.size
                border = []
                for x in range(w_s):
                    border.append(px[x, 0])
                    border.append(px[x, h_s - 1])
                for y in range(h_s):
                    border.append(px[0, y])
                    border.append(px[w_s - 1, y])
                bg = tuple(int(sum(c[i] for c in border) / max(1, len(border))) for i in range(3))
                active_cols = []
                for x in range(w_s):
                    count = 0
                    for y in range(h_s):
                        r, g, b = px[x, y]
                        dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                        if dist > 60:
                            count += 1
                    active_cols.append(count >= max(10, int(h_s * 0.18)))
                v_segments = 0
                run = 0
                min_run = max(8, int(w_s * 0.06))
                for flag in active_cols:
                    if flag:
                        run += 1
                    else:
                        if run >= min_run:
                            v_segments += 1
                        run = 0
                if run >= min_run:
                    v_segments += 1
                active_rows = []
                for y in range(h_s):
                    count = 0
                    for x in range(w_s):
                        r, g, b = px[x, y]
                        dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                        if dist > 60:
                            count += 1
                    active_rows.append(count >= max(10, int(w_s * 0.18)))
                h_segments = 0
                run = 0
                min_run_h = max(8, int(h_s * 0.06))
                for flag in active_rows:
                    if flag:
                        run += 1
                    else:
                        if run >= min_run_h:
                            h_segments += 1
                        run = 0
                if run >= min_run_h:
                    h_segments += 1
                segments = max(v_segments, h_segments)
                if light_bg > 0.30 and segments >= 3:
                    return True, f"character_sheet_layout (light_bg={light_bg:.2f}, v_segments={v_segments}, h_segments={h_segments})"
                if light_bg > 0.25 and v_segments >= 2:
                    return True, f"split_panel_layout (light_bg={light_bg:.2f}, v_segments={v_segments}, h_segments={h_segments})"
                if segments >= 4:
                    return True, f"multi_panel_detected (v_segments={v_segments}, h_segments={h_segments})"
                if v_segments >= 2 and h_segments >= 2:
                    return True, f"grid_layout (v_segments={v_segments}, h_segments={h_segments})"
                return False, f"single_panel (light_bg={light_bg:.2f}, v_segments={v_segments}, h_segments={h_segments})"
        except Exception as exc:
            return False, f"check_failed: {exc}"

    # ------------------------------------------------------------------
    # Last frame extraction (for continuity chain)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_last_frame(video_path: Path, out_path: Path) -> bool:
        """Extract the last clean frame from a normalized MP4 as PNG."""
        try:
            ff = shutil.which("ffmpeg")
            if not ff:
                return False
            cp = subprocess.run(
                [ff, "-hide_banner", "-loglevel", "error", "-i", str(video_path),
                 "-vf", "reverse", "-vframes", "1", "-q:v", "2", str(out_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            )
            if cp.returncode != 0 or not out_path.is_file():
                cp = subprocess.run(
                    [ff, "-hide_banner", "-loglevel", "error", "-i", str(video_path),
                     "-vf", "select=eq(n\\,0)", "-vframes", "1", "-q:v", "2", str(out_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
            return cp.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 1000
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Image similarity (identity proxy when no vision evaluator)
    # ------------------------------------------------------------------

    @staticmethod
    def _image_similarity(a: Path, b: Path) -> dict:
        """Compare two images for identity continuity.
        Returns dict with: identity_score, outfit_match, weapon_match (all 0-1).
        """
        try:
            with Image.open(a) as im_a, Image.open(b) as im_b:
                im_a = im_a.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
                im_b = im_b.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
                diff = ImageChops.difference(im_a, im_b)
                stat = ImageStat.Stat(diff)
                rms = sum(stat.mean) / 3
                identity_score = max(0.0, 1.0 - rms / 128.0)
                lower_a = im_a.crop((0, 128, 256, 256))
                lower_b = im_b.crop((0, 128, 256, 256))
                hist_a = lower_a.histogram()
                hist_b = lower_b.histogram()
                hist_sum = sum(hist_a)
                if hist_sum > 0:
                    hist_a = [h / hist_sum for h in hist_a]
                hist_sum_b = sum(hist_b)
                if hist_sum_b > 0:
                    hist_b = [h / hist_sum_b for h in hist_b]
                outfit_match = 1.0 - sum(abs(ha - hb) for ha, hb in zip(hist_a, hist_b)) / 2.0
                right_a = im_a.crop((170, 0, 256, 256)).filter(ImageFilter.FIND_EDGES)
                right_b = im_b.crop((170, 0, 256, 256)).filter(ImageFilter.FIND_EDGES)
                edge_a = ImageStat.Stat(right_a).mean[0]
                edge_b = ImageStat.Stat(right_b).mean[0]
                weapon_match = max(0.0, 1.0 - abs(edge_a - edge_b) / 50.0)
                return {
                    "identity_score": round(identity_score, 4),
                    "outfit_match": round(outfit_match, 4),
                    "weapon_match": round(weapon_match, 4),
                }
        except Exception as exc:
            return {"identity_score": 0.0, "outfit_match": 0.0, "weapon_match": 0.0, "error": str(exc)}

    # ------------------------------------------------------------------
    # Face model loading (YuNet + SFace) — human subjects only
    # ------------------------------------------------------------------

    _yunet_detector = None
    _sface_recognizer = None
    _subject_type_cache: dict[str, str] = {}

    @classmethod
    def _get_face_detector(cls):
        """Lazily load YuNet face detector. Copies ONNX to temp dir for Unicode path safety."""
        if cls._yunet_detector is not None:
            return cls._yunet_detector
        try:
            import cv2
            import tempfile
            models_dir = Path(__file__).parent / "face_models"
            model_path = models_dir / "face_detection_yunet_2023mar.onnx"
            if not model_path.is_file():
                return None
            tmp_dir = Path(tempfile.gettempdir()) / "face_models_cache"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_model = tmp_dir / "face_detection_yunet_2023mar.onnx"
            if not tmp_model.is_file() or tmp_model.stat().st_size != model_path.stat().st_size:
                shutil.copy2(str(model_path), str(tmp_model))
            detector = cv2.FaceDetectorYN_create(str(tmp_model), "", (320, 320))
            cls._yunet_detector = detector
            return detector
        except Exception:
            return None

    @classmethod
    def _get_face_recognizer(cls):
        """Lazily load SFace face recognizer. Copies ONNX to temp dir for Unicode path safety."""
        if cls._sface_recognizer is not None:
            return cls._sface_recognizer
        try:
            import cv2
            import tempfile
            models_dir = Path(__file__).parent / "face_models"
            model_path = models_dir / "face_recognition_sface_2021dec.onnx"
            if not model_path.is_file():
                return None
            tmp_dir = Path(tempfile.gettempdir()) / "face_models_cache"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_model = tmp_dir / "face_recognition_sface_2021dec.onnx"
            if not tmp_model.is_file() or tmp_model.stat().st_size != model_path.stat().st_size:
                shutil.copy2(str(model_path), str(tmp_model))
            recognizer = cv2.FaceRecognizerSF_create(str(tmp_model), "")
            cls._sface_recognizer = recognizer
            return recognizer
        except Exception:
            return None

    @staticmethod
    def _detect_faces(path: Path) -> list[tuple]:
        """Detect face ROIs using YuNet. Uses imdecode for Unicode path safety."""
        try:
            import cv2
            import numpy as np
            with open(str(path), "rb") as f:
                raw = f.read()
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return []
            h, w = image.shape[:2]
            detector = AutoProducer._get_face_detector()
            if detector is None:
                return []
            detector.setInputSize((w, h))
            _, faces = detector.detect(image)
            if faces is None or len(faces) == 0:
                return []
            result = []
            for f in faces:
                x, y, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                lm = {
                    "reye": (float(f[4]), float(f[5])),
                    "leye": (float(f[6]), float(f[7])),
                    "nose": (float(f[8]), float(f[9])),
                    "rmouth": (float(f[10]), float(f[11])),
                    "lmouth": (float(f[12]), float(f[13])),
                }
                result.append((x, y, fw, fh, lm))
            return result
        except Exception:
            return []

    @staticmethod
    def _extract_face_embedding(path: Path) -> list[float] | None:
        """Extract 128-dim SFace embedding. Returns None if no face or model unavailable."""
        try:
            import cv2
            import numpy as np
            with open(str(path), "rb") as f:
                raw = f.read()
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return None
            h, w = image.shape[:2]
            detector = AutoProducer._get_face_detector()
            recognizer = AutoProducer._get_face_recognizer()
            if detector is None or recognizer is None:
                return None
            detector.setInputSize((w, h))
            _, faces = detector.detect(image)
            if faces is None or len(faces) == 0:
                return None
            aligned = recognizer.alignCrop(image, faces[0])
            embedding = recognizer.feature(aligned)
            return embedding.flatten().tolist()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Subject classification — human vs non_human
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_subject_type(path: Path) -> str:
        """Classify subject as 'human' or 'non_human' based on current image.
        YuNet face detection: if face found → human, else → non_human.
        """
        cache_key = str(path)
        if cache_key in AutoProducer._subject_type_cache:
            return AutoProducer._subject_type_cache[cache_key]
        faces = AutoProducer._detect_faces(path)
        if len(faces) >= 1:
            result = "human"
        else:
            result = "non_human"
        AutoProducer._subject_type_cache[cache_key] = result
        return result

    # ------------------------------------------------------------------
    # Non-human anatomy gate (anthropomorphic animals, robots, etc.)
    # ------------------------------------------------------------------

    @staticmethod
    def _non_human_anatomy_check(path: Path, master_face: Path | None = None) -> dict:
        """Anatomy gate for non-human subjects. Uses heuristics:
        1. Verify image has real content (not blank)
        2. Check for multi-panel / duplicate subject
        3. Gradient discontinuity for distortion
        4. Master reference comparison (color histogram + pixel diff)
        """
        try:
            with Image.open(path) as im:
                im.load()
                rgb = im.convert("RGB")

                # Step 1: Not blank
                sample = rgb.resize((128, 128), Image.Resampling.BILINEAR)
                pixels = list(sample.getdata())
                colors = set((r // 32, g // 32, b // 32) for r, g, b in pixels)
                if len(colors) < 5:
                    return {"pass": False, "score": 0.0, "reason": "BLANK_IMAGE: too few distinct colors"}

                # Step 2: Multi-panel check
                is_multi, multi_reason = AutoProducer._is_multi_panel_image(path)
                if is_multi:
                    return {"pass": False, "score": 0.15, "reason": f"MULTI_PANEL: {multi_reason}"}

                # Step 3: Duplicate subject (vertical segmentation)
                from PIL import ImageOps
                import numpy as np
                gray = sample.convert("L")
                arr = np.array(gray, dtype=np.float64)
                bg_val = arr[0, 0]
                col_active = np.mean(np.abs(arr - bg_val), axis=0)
                col_threshold = np.mean(col_active) * 1.2
                active_cols = col_active > col_threshold
                segments = 0
                in_seg = False
                seg_widths = []
                cur_width = 0
                for a in active_cols:
                    if a:
                        if not in_seg:
                            in_seg = True
                        cur_width += 1
                    else:
                        if in_seg:
                            if cur_width >= 8:
                                segments += 1
                                seg_widths.append(cur_width)
                            in_seg = False
                            cur_width = 0
                if in_seg and cur_width >= 8:
                    segments += 1
                    seg_widths.append(cur_width)
                if segments >= 2 and all(w >= 20 for w in seg_widths):
                    return {"pass": False, "score": 0.20, "reason": f"DUPLICATE_SUBJECT: {segments} vertical segments"}

                # Step 4: Gradient discontinuity
                grad_h = np.abs(np.diff(arr, axis=1))
                grad_mean = grad_h.mean()
                grad_max = grad_h.max()
                grad_ratio = grad_max / grad_mean if grad_mean > 1 else 0
                distortion_score = 1.0
                distortion_reason = "gradient_ok"
                if grad_ratio > 40:
                    distortion_score = 0.3
                    distortion_reason = f"grad_spike={grad_ratio:.1f}"
                elif grad_ratio > 30:
                    distortion_score = 0.6
                    distortion_reason = f"grad_high={grad_ratio:.1f}"

                # Step 5: Master reference comparison
                master_score = 1.0
                master_reason = "no_master"
                if master_face is not None:
                    try:
                        with Image.open(master_face) as mf:
                            mf_rgb = mf.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
                            curr = rgb.resize((256, 256), Image.Resampling.BILINEAR)
                            curr_eq = ImageOps.equalize(curr)
                            mast_eq = ImageOps.equalize(mf_rgb)
                            diff = ImageChops.difference(curr_eq, mast_eq)
                            mstat = ImageStat.Stat(diff)
                            m_rms = sum(mstat.mean) / 3
                            hist_c = curr.histogram()
                            hist_m = mf_rgb.histogram()
                            sc = sum(hist_c)
                            sm = sum(hist_m)
                            if sc > 0:
                                hist_c = [h / sc for h in hist_c]
                            if sm > 0:
                                hist_m = [h / sm for h in hist_m]
                            hist_sim = 1.0 - sum(abs(hc - hm) for hc, hm in zip(hist_c, hist_m)) / 2.0
                            pixel_score = max(0.0, 1.0 - m_rms / 80.0)
                            master_score = pixel_score * 0.5 + hist_sim * 0.5
                            master_reason = f"pixel={pixel_score:.3f} hist={hist_sim:.3f} rms={m_rms:.1f}"
                    except Exception as exc:
                        master_reason = f"master_error: {exc}"

                content_score = 1.0
                combined = distortion_score * 0.40 + master_score * 0.40 + content_score * 0.20
                passed = combined >= 0.50
                reason = (
                    f"distortion={distortion_score:.3f}({distortion_reason}) "
                    f"master={master_score:.3f}({master_reason}) "
                    f"segments={segments} combined={combined:.3f}"
                )
                return {
                    "pass": passed,
                    "score": round(combined, 4),
                    "reason": reason,
                    "scores": {
                        "distortion": round(distortion_score, 4),
                        "master_reference": round(master_score, 4),
                        "content_validity": round(content_score, 4),
                    },
                }
        except Exception as exc:
            return {"pass": False, "score": 0.0, "reason": f"check_error: {exc}"}

    # ------------------------------------------------------------------
    # Human face anatomy gate (YuNet + SFace)
    # ------------------------------------------------------------------

    @staticmethod
    def _human_face_anatomy_check(path: Path, master_face: Path | None = None) -> dict:
        """Face anatomy gate for HUMAN subjects using YuNet + SFace.

        1. Detect face ROIs — 0 faces = FAIL, 2+ = FAIL (duplicate)
        2. Landmark geometric consistency + local gradient discontinuity
        3. Edge structure (secondary)
        4. Duplicate features within ROI
        5. Symmetry (secondary, capped)
        6. Master face comparison via SFace cosine + pixel ROI
        """
        import math
        import numpy as np
        from PIL import ImageOps

        faces = AutoProducer._detect_faces(path)
        face_count = len(faces)

        if face_count == 0:
            return {"pass": False, "score": 0.0, "reason": "FACE_NOT_FOUND: no face detected by YuNet"}
        if face_count >= 2:
            return {"pass": False, "score": 0.15, "reason": f"DUPLICATE_FACE: {face_count} faces detected"}

        fx, fy, fw, fh, landmarks = faces[0]

        try:
            with Image.open(path) as im:
                im.load()
                rgb = im.convert("RGB")
                img_w, img_h = rgb.size
                pad_x = int(fw * 0.15); pad_y = int(fh * 0.20)
                cx0 = max(0, fx - pad_x); cy0 = max(0, fy - pad_y)
                cx1 = min(img_w, fx + fw + pad_x); cy1 = min(img_h, fy + fh + pad_y)
                face_crop = rgb.crop((cx0, cy0, cx1, cy1)).resize((128, 128), Image.Resampling.BILINEAR)

                # Landmark geometric consistency
                lm = landmarks
                geom_issues = []
                geom_score = 0.9
                reye = lm["reye"]; leye = lm["leye"]
                nose = lm["nose"]
                rmouth = lm["rmouth"]; lmouth = lm["lmouth"]

                eye_y_diff = abs(reye[1] - leye[1])
                eye_y_threshold = fh * 0.15
                if eye_y_diff > eye_y_threshold:
                    geom_issues.append(f"eye_y_misalign={eye_y_diff:.1f}")
                    geom_score -= 0.35

                eye_left_x = min(reye[0], leye[0])
                eye_right_x = max(reye[0], leye[0])
                eye_mid_x = (reye[0] + leye[0]) / 2
                nose_offset = abs(nose[0] - eye_mid_x)
                nose_offset_ratio = nose_offset / max(1, (eye_right_x - eye_left_x))
                if nose_offset_ratio > 1.5:
                    geom_issues.append(f"nose_x_off={nose_offset_ratio:.2f}")
                    geom_score -= 0.25

                mouth_y = (rmouth[1] + lmouth[1]) / 2
                if mouth_y < nose[1] - fh * 0.02:
                    geom_issues.append("mouth_above_nose")
                    geom_score -= 0.40

                mouth_w = abs(lmouth[0] - rmouth[0])
                eye_w = abs(leye[0] - reye[0])
                if eye_w > 1 and mouth_w > eye_w * 1.8:
                    geom_issues.append(f"mouth_too_wide={mouth_w/eye_w:.2f}")
                    geom_score -= 0.25

                if eye_w > 0:
                    eye_spacing_ratio = eye_w / fw
                    if eye_spacing_ratio < 0.15 or eye_spacing_ratio > 0.70:
                        geom_issues.append(f"eye_spacing={eye_spacing_ratio:.2f}")
                        geom_score -= 0.20

                # Local gradient discontinuity
                gray_crop = np.array(face_crop.convert("L"), dtype=np.float64)
                grad_h = np.abs(np.diff(gray_crop, axis=1))
                grad_mean = grad_h.mean()
                grad_max = grad_h.max()
                grad_ratio = grad_max / grad_mean if grad_mean > 1 else 0
                if grad_ratio > 35:
                    geom_issues.append(f"grad_spike_ratio={grad_ratio:.1f}")
                    geom_score -= 0.40
                elif grad_ratio > 25:
                    geom_issues.append(f"grad_high_ratio={grad_ratio:.1f}")
                    geom_score -= 0.15

                geom_score = max(0.0, min(1.0, geom_score))
                geom_reason = "geom_ok" if not geom_issues else ";".join(geom_issues)

                # Edge structure
                edges = face_crop.filter(ImageFilter.FIND_EDGES).convert("L")
                ew, eh = edges.size
                band_h = eh // 3
                band_densities = []
                for bi in range(3):
                    by0 = bi * band_h; by1 = min((bi + 1) * band_h, eh)
                    band = edges.crop((0, by0, ew, by1))
                    band_densities.append(ImageStat.Stat(band).mean[0])
                mid_is_highest = band_densities[1] >= band_densities[0] and band_densities[1] >= band_densities[2]
                mean_edge = sum(band_densities) / 3
                if mean_edge < 3:
                    edge_score = 0.2; edge_reason = "too_flat_no_features"
                elif mid_is_highest and mean_edge < 80:
                    edge_score = 0.8; edge_reason = "structured"
                elif mid_is_highest:
                    edge_score = 0.7; edge_reason = "structured_high_edge"
                else:
                    edge_score = 0.25; edge_reason = "feature_misplacement"

                # Duplicate features
                edge_data = list(edges.getdata())
                strip_w = 16
                num_strips = ew // strip_w
                strip_densities = []
                for si in range(num_strips):
                    sx0 = si * strip_w
                    s_sum = 0; s_count = 0
                    for py in range(eh):
                        for px in range(sx0, min(sx0 + strip_w, ew)):
                            s_sum += edge_data[py * ew + px]; s_count += 1
                    strip_densities.append(s_sum / max(1, s_count))
                g_mean = sum(strip_densities) / max(1, len(strip_densities)) if strip_densities else 0
                thresh = max(10, g_mean * 1.4)
                clusters = 0; in_cluster = False
                for sd in strip_densities:
                    if sd > thresh:
                        if not in_cluster: clusters += 1; in_cluster = True
                    else:
                        in_cluster = False
                if clusters >= 3:
                    dup_feature_score = 0.2; dup_reason = f"duplicate_features clusters={clusters}"
                elif clusters == 2:
                    dup_feature_score = 0.6; dup_reason = f"possible_duplicate clusters={clusters}"
                else:
                    dup_feature_score = 0.9; dup_reason = "single_feature_set"

                # Symmetry (secondary, capped)
                fw2, fh2 = face_crop.size
                left = face_crop.crop((0, 0, fw2 // 2, fh2))
                right = face_crop.crop((fw2 // 2, 0, fw2, fh2))
                right_mirrored = right.transpose(Image.FLIP_LEFT_RIGHT)
                sym_diff = ImageChops.difference(left, right_mirrored)
                sym_stat = ImageStat.Stat(sym_diff)
                sym_rms = sum(sym_stat.mean) / 3
                symmetry_score = max(0.0, 1.0 - sym_rms / 90.0)
                symmetry_capped = min(symmetry_score, 0.65)

                # Master face comparison (SFace embeddings + pixel ROI)
                master_score = 1.0; master_reason = "no_master"
                master_hard_veto = False
                master_cosine = None
                pixel_distortion_score = 1.0; pixel_distortion_reason = "no_master"
                if master_face is not None:
                    emb1 = AutoProducer._extract_face_embedding(path)
                    emb2 = AutoProducer._extract_face_embedding(master_face)
                    if emb1 is not None and emb2 is not None:
                        dot = sum(a * b for a, b in zip(emb1, emb2))
                        norm1 = math.sqrt(sum(a * a for a in emb1))
                        norm2 = math.sqrt(sum(b * b for b in emb2))
                        if norm1 > 0 and norm2 > 0:
                            cosine_sim = dot / (norm1 * norm2)
                            master_cosine = cosine_sim
                            master_score = 1.0 / (1.0 + math.exp(-12.0 * (cosine_sim - 0.363)))
                            master_score = max(0.0, min(1.0, master_score))
                            master_reason = f"embedding_cosine={cosine_sim:.3f}"
                            if cosine_sim < 0.30:
                                master_hard_veto = True
                                master_reason = f"IDENTITY_MISMATCH cosine={cosine_sim:.3f} < 0.30"
                        else:
                            master_reason = "embedding_zero_norm"
                    else:
                        master_reason = "embedding_unavailable"

                    # Pixel-level face ROI comparison
                    master_faces = AutoProducer._detect_faces(master_face)
                    if len(master_faces) == 1:
                        mfx, mfy, mfw, mfh = master_faces[0][:4]
                        with Image.open(master_face) as mf:
                            mf_rgb = mf.convert("RGB")
                            mw_img, mh_img = mf_rgb.size
                            mpad_x = int(mfw * 0.15); mpad_y = int(mfh * 0.20)
                            mcx0 = max(0, mfx - mpad_x); mcy0 = max(0, mfy - mpad_y)
                            mcx1 = min(mw_img, mfx + mfw + mpad_x); mcy1 = min(mh_img, mfy + mfh + mpad_y)
                            master_crop = mf_rgb.crop((mcx0, mcy0, mcx1, mcy1)).resize((128, 128), Image.Resampling.BILINEAR)
                            face_norm = ImageOps.equalize(face_crop.convert("RGB"))
                            master_norm = ImageOps.equalize(master_crop.convert("RGB"))
                            diff = ImageChops.difference(face_norm, master_norm)
                            mstat = ImageStat.Stat(diff)
                            m_rms = sum(mstat.mean) / 3
                            if not master_hard_veto and master_cosine is not None and master_cosine >= 0.363:
                                cosine_degradation = 0.0
                                if master_cosine < 0.75:
                                    cosine_degradation = (0.75 - master_cosine) / 0.35
                                    cosine_degradation = max(0.0, min(1.0, cosine_degradation))
                                if m_rms > 12:
                                    pixel_component = max(0.0, 1.0 - (m_rms - 8) / 18.0)
                                else:
                                    pixel_component = 1.0
                                if master_cosine < 0.60:
                                    pixel_distortion_score = min(pixel_component, 1.0 - cosine_degradation * 0.8)
                                else:
                                    pixel_distortion_score = min(pixel_component, 1.0 - cosine_degradation * 0.4)
                                pixel_distortion_reason = f"warp rms={m_rms:.1f} cosine={master_cosine:.3f} degr={cosine_degradation:.2f}"
                            else:
                                if not master_hard_veto:
                                    master_score = max(0.0, 1.0 - m_rms / 70.0)
                                    master_reason = f"pixel_fallback score={master_score:.3f}"
                    else:
                        pixel_distortion_reason = f"master_face_count={len(master_faces)}"

                # Combined score
                combined = (
                    geom_score * 0.25 +
                    edge_score * 0.15 +
                    dup_feature_score * 0.15 +
                    master_score * 0.20 +
                    pixel_distortion_score * 0.15 +
                    symmetry_capped * 0.10
                )

                if master_hard_veto:
                    combined = 0.0
                    passed = False
                    reason = (
                        f"IDENTITY_VETO: {master_reason} "
                        f"geom={geom_score:.3f}({geom_reason}) "
                        f"master={master_score:.3f} combined=0.000 (vetoed)"
                    )
                elif pixel_distortion_score < 0.50 and master_cosine is not None and master_cosine >= 0.363:
                    combined = min(combined, 0.40)
                    passed = False
                    reason = (
                        f"WARP_VETO: {pixel_distortion_reason} "
                        f"geom={geom_score:.3f}({geom_reason}) "
                        f"master={master_score:.3f}({master_reason}) "
                        f"pixel_distortion={pixel_distortion_score:.3f} "
                        f"combined={combined:.3f} (capped)"
                    )
                else:
                    passed = combined >= 0.50
                    reason = (
                        f"geom={geom_score:.3f}({geom_reason}) edge={edge_score:.3f}({edge_reason}) "
                        f"dup={dup_feature_score:.3f}({dup_reason}) "
                        f"sym={symmetry_score:.3f}(capped={symmetry_capped:.3f}) "
                        f"master={master_score:.3f}({master_reason}) "
                        f"warp={pixel_distortion_score:.3f}({pixel_distortion_reason}) "
                        f"combined={combined:.3f} face_roi=({fx},{fy},{fw},{fh})"
                    )
                return {
                    "pass": passed,
                    "score": round(combined, 4),
                    "reason": reason,
                    "face_found": True,
                    "face_count": 1,
                    "face_roi": [int(fx), int(fy), int(fw), int(fh)],
                    "scores": {
                        "landmark_geometry": round(geom_score, 4),
                        "edge_structure": round(edge_score, 4),
                        "duplicate_feature": round(dup_feature_score, 4),
                        "symmetry": round(symmetry_score, 4),
                        "master_face": round(master_score, 4),
                        "master_cosine": round(master_cosine, 4) if master_cosine is not None else None,
                        "pixel_distortion": round(pixel_distortion_score, 4),
                    },
                }
        except Exception as exc:
            return {"pass": False, "score": 0.0, "reason": f"check_error: {exc}"}

    # ------------------------------------------------------------------
    # Subject-aware anatomy gate dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _face_anatomy_check(path: Path, master_face: Path | None = None) -> dict:
        """Subject-aware anatomy gate. Dispatches to human or non_human checker.
        Adds SUBJECT_TYPE, FACE_GATE_MODE, REFERENCE_MATCH to result.
        """
        subject_type = AutoProducer._classify_subject_type(path)
        gate_mode = "dnn" if subject_type == "human" else "non_human_heuristic"
        has_master = master_face is not None

        if subject_type == "human":
            result = AutoProducer._human_face_anatomy_check(path, master_face=master_face)
        else:
            result = AutoProducer._non_human_anatomy_check(path, master_face=master_face)

        result["subject_type"] = subject_type
        result["face_gate_mode"] = gate_mode
        result["reference_match"] = "with_master" if has_master else "no_master"
        return result

    # ------------------------------------------------------------------
    # SRT / TTS / Audio helpers (unchanged)
    # ------------------------------------------------------------------

    @staticmethod
    def _srt_time(seconds: float) -> str:
        ms = int(round(max(0.0, seconds) * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _write_srt(self, plan: dict, path: Path):
        lines = []
        for idx, scene in enumerate(plan.get("scenes") or [], 1):
            text = str(scene.get("caption") or scene.get("voice") or "").strip()
            if not text:
                continue
            lines += [str(idx), f"{self._srt_time(parse_duration(scene.get('start') or 0))} --> {self._srt_time(parse_duration(scene.get('end') or 0))}", text, ""]
        path.write_text("\n".join(lines), encoding="utf-8-sig")
        return path

    @staticmethod
    def _powershell() -> str | None:
        return shutil.which("powershell") or shutil.which("pwsh")

    def _tts_scene(self, text: str, wav: Path, rate: int = 0) -> bool:
        ps = self._powershell()
        if not ps or os.name != "nt":
            return False
        txt = wav.with_suffix(".txt")
        script = wav.with_suffix(".ps1")
        txt.write_text(text, encoding="utf-8")
        script.write_text(
            "Add-Type -AssemblyName System.Speech\n"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            f"$s.Rate = {max(-5, min(5, int(rate)))}\n"
            f"$t = [IO.File]::ReadAllText('{str(txt).replace("'", "''")}', [Text.Encoding]::UTF8)\n"
            f"$s.SetOutputToWaveFile('{str(wav).replace("'", "''")}')\n"
            "$s.Speak($t)\n$s.Dispose()\n",
            encoding="utf-8-sig",
        )
        try:
            cp = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            return cp.returncode == 0 and wav.is_file() and wav.stat().st_size > 44
        finally:
            txt.unlink(missing_ok=True)
            script.unlink(missing_ok=True)

    def _build_voice_track(self, plan: dict, folder: Path, duration: float) -> Path | None:
        clips = []
        for i, scene in enumerate(plan.get("scenes") or [], 1):
            text = str(scene.get("voice") or "").strip()
            if not text:
                continue
            wav = folder / f"voice_{i:02d}.wav"
            if self._tts_scene(text, wav):
                clips.append((wav, int(round(parse_duration(scene.get("start") or 0) * 1000))))
        if not clips:
            return None
        ff = self._ffmpeg()
        out = folder / "voice_mix.wav"
        args = [ff, "-hide_banner", "-loglevel", "error", "-y"]
        for wav, _ in clips:
            args += ["-i", str(wav)]
        filters, labels = [], []
        for i, (_, delay) in enumerate(clips):
            labels.append(f"[v{i}]")
            filters.append(f"[{i}:a]adelay={delay}|{delay},volume=1.0[v{i}]")
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{duration:.3f}[a]")
        args += ["-filter_complex", ";".join(filters), "-map", "[a]", "-ac", "2", "-ar", "48000", str(out)]
        cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out if cp.returncode == 0 and out.exists() else None

    def _pick_music(self, plan: dict) -> Path | None:
        lib = getattr(self.app.state, "music_library", None)
        if lib is None:
            return None
        wish = str((plan.get("music_plan") or {}).get("mood") or "cinematic")
        try:
            result = lib.search(wish, 1)
            items = result.get("items") or []
            return Path(lib.path(items[0]["id"])) if items else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # FFmpeg encoding helpers (unchanged — do NOT touch FFmpeg core)
    # ------------------------------------------------------------------

    _nvenc_cache = None
    def _has_nvenc(self) -> bool:
        if self._nvenc_cache is not None:
            return self._nvenc_cache
        try:
            cp = subprocess.run([self._ffmpeg(), "-hide_banner", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            self._nvenc_cache = b"h264_nvenc" in cp.stdout
        except Exception:
            self._nvenc_cache = False
        return self._nvenc_cache

    def _encode_args(self, quality: str) -> tuple[str, list[str]]:
        if self._has_nvenc():
            if quality == "final":
                return "h264_nvenc", ["-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0"]
            if quality == "high":
                return "h264_nvenc", ["-preset", "p5", "-tune", "hq", "-cq", "18"]
            return "h264_nvenc", ["-preset", "p4", "-cq", "21"]
        if quality == "final":
            return "libx264", ["-preset", "slow", "-crf", "17"]
        if quality == "high":
            return "libx264", ["-preset", "medium", "-crf", "18"]
        return "libx264", ["-preset", "veryfast", "-crf", "20"]

    def _normalize_clip(self, src: Path, dst: Path, ratio: str, fps=30, quality="balanced"):
        ff = self._ffmpeg()
        w, h = self._ratio_size(ratio, quality)
        sharpen = ",unsharp=5:5:0.35:5:5:0.0" if quality in {"high", "final"} else ""
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},fps={fps}{sharpen},format=yuv420p"
        enc, encargs = self._encode_args(quality)
        # Atomic: write to .tmp.mp4, then rename
        tmp_dst = AutoProducer._tmp_path(dst)
        args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-an", "-vf", vf, "-r", str(fps), "-fps_mode", "cfr", "-c:v", enc, *encargs, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp_dst)]
        cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0 and enc == "h264_nvenc":
            args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-an", "-vf", vf, "-r", str(fps), "-fps_mode", "cfr", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp_dst)]
            cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.decode("utf-8", "replace")[-1500:])
        # Atomic rename: .tmp.mp4 → final
        tmp_dst.replace(dst)

    def _concat(self, clips: list[Path], out: Path):
        if not clips:
            raise RuntimeError("Không có scene video để ghép")
        lst = out.with_suffix(".concat.txt")
        lst.write_text("\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips), encoding="utf-8")
        tmp_out = AutoProducer._tmp_path(out)
        cp = subprocess.run([self._ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(tmp_out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.decode("utf-8", "replace")[-1500:])
        tmp_out.replace(out)
        return out

    def _final_mix(self, video: Path, voice: Path | None, music: Path | None, out: Path, duration: float):
        ff = self._ffmpeg()
        tmp_out = AutoProducer._tmp_path(out)
        args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
        if voice:
            args += ["-i", str(voice)]
        if music:
            args += ["-stream_loop", "-1", "-i", str(music)]
        if voice and music:
            args += ["-filter_complex", f"[1:a]volume=1.0[v];[2:a]volume=0.16,atrim=0:{duration:.3f}[m];[v][m]amix=inputs=2:normalize=0:duration=longest[a]", "-map", "0:v:0", "-map", "[a]"]
        elif voice:
            args += ["-map", "0:v:0", "-map", "1:a:0"]
        elif music:
            args += ["-filter_complex", f"[1:a]volume=0.16,atrim=0:{duration:.3f}[a]", "-map", "0:v:0", "-map", "[a]"]
        else:
            args += ["-map", "0:v:0"]
        args += ["-c:v", "copy"]
        if voice or music:
            args += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        args += ["-movflags", "+faststart", str(tmp_out)]
        cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.decode("utf-8", "replace")[-1500:])
        tmp_out.replace(out)
        return out

    def _final_master(self, src: Path, out: Path, ratio: str, quality: str):
        if quality not in {"high", "final"}:
            shutil.copy2(src, out)
            return out
        ff = self._ffmpeg()
        w, h = self._ratio_size(ratio, quality)
        enc, encargs = self._encode_args(quality)
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},unsharp=5:5:0.30:5:5:0.0,format=yuv420p"
        tmp_out = AutoProducer._tmp_path(out)
        args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf, "-c:v", enc, *encargs, "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp_out)]
        cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0 and enc == "h264_nvenc":
            args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp_out)]
            cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.decode("utf-8", "replace")[-1500:])
        tmp_out.replace(out)
        return out

    # ==================================================================
    # LINEAR PIPELINE — 5 stages per scene
    # ==================================================================

    # --- Stage 1: prepare_reference ---
    def _prepare_reference(self, plan: dict, folder: Path, cancel_event, progress, quality: str) -> Path | None:
        """Prepare character anchor (master reference) for the whole production.
        Scene 1 = MASTER_REFERENCE. Returns the anchor path or None.
        """
        uploaded_reference = self._uploaded_reference_path(plan)
        if uploaded_reference is not None:
            progress(2, "Character Reference", "Đang khóa nhân vật theo ảnh người dùng")
            anchor = folder / "character_anchor.png"
            shutil.copy2(uploaded_reference, anchor)
            # Factory patch 30/09: ảnh nhỏ cạnh ngắn <768 được phóng to Lanczos trước QA
            # — hết chặn pipeline vì IMAGE_RESOLUTION_LOW (ngưỡng QA là 512).
            try:
                from PIL import Image as _PILImage
                with _PILImage.open(anchor) as _im:
                    _w, _h = _im.size
                    if min(_w, _h) < 768:
                        _scale = 768.0 / min(_w, _h)
                        _up = _im.convert("RGB").resize((round(_w * _scale), round(_h * _scale)), _PILImage.LANCZOS)
                        _up.save(anchor, format="PNG")
            except Exception:
                pass  # upscale lỗi thì để QA phán như cũ
            qa = image_quality(anchor)
            if not qa.passed:
                raise RuntimeError("CHARACTER_REFERENCE_QA_FAILED: " + ", ".join(qa.issues or []))
            progress(6, "Character Reference", "Ảnh tham chiếu PASS · dùng làm source of truth")
            return anchor

        if self._looks_character_based(plan):
            progress(2, "Character Lock", "Tạo ảnh chuẩn nhân vật trước khi sinh các cảnh")
            anchor = folder / "character_anchor.png"
            anchor_meta = self._generate_character_anchor(plan, anchor, cancel_event,
                lambda p, s, d="": progress(2 + int(p * 0.06), s, d), quality)
            if anchor_meta and anchor_meta.get("failed"):
                raise RuntimeError("CHARACTER_ANCHOR_QA_FAILED")
            return anchor

        return None

    def _generate_character_anchor(self, plan: dict, out: Path, cancel_event, progress, quality: str) -> dict | None:
        if not self._looks_character_based(plan):
            return None
        svc = getattr(self.app.state, "ai_image_service", None)
        if svc is None:
            raise RuntimeError("Module tao_anh_ai chưa được mount vào app.state.ai_image_service")
        ratio = str((plan.get("concept") or {}).get("aspect_ratio") or "16:9")
        style = self._style_for_plan(plan)
        size = self._image_size_for_ratio(ratio)
        prompt = self._anchor_prompt(plan)
        attempts = []
        for attempt in range(1, MAX_IMAGE_ATTEMPTS + 1):
            if cancel_event.is_set():
                raise AutoProduceCancelled("Đã dừng")
            suffix = "" if attempt == 1 else " Extra quality pass: single character only, crisp detailed face, correct eyes and mouth, clean anatomy, no blur."
            data = self._call_compat(
                svc.generate, prompt + suffix, style, size, "high",
                cancel_event=cancel_event,
                progress=lambda p, s, d="": progress(p, f"Character Anchor · {s}", d),
            )
            if not isinstance(data, (bytes, bytearray)):
                raise RuntimeError("tao_anh_ai không trả image bytes hợp lệ cho character anchor")
            out.write_bytes(bytes(data))
            qa = image_quality(out)
            attempts.append({"attempt": attempt, "qa": qa.as_dict()})
            if qa.passed:
                return {"path": str(out), "prompt": prompt, "style": style, "size": size, "attempts": attempts, "qa": qa.as_dict()}
        return {"path": str(out), "prompt": prompt, "style": style, "size": size, "attempts": attempts, "qa": attempts[-1]["qa"], "failed": True}

    # --- Stage 2: generate_image ---
    def _generate_image(self, scene: dict, plan: dict, out: Path, cancel_event, progress, *,
                        quality: str, anchor: Path | None = None,
                        continuity_anchor: Path | None = None, scene_id: int = 0,
                        fast_mode: bool = False, retry: bool = False) -> dict:
        """Generate one scene image. Called once per attempt.
        The caller (produce) handles retry by calling this again with retry=True.
        Uses img2img (svc.edit) when anchor or continuity_anchor is available.
        No face/anatomy/identity check here — that's in validate_image.
        """
        svc = getattr(self.app.state, "ai_image_service", None)
        if svc is None:
            raise RuntimeError("Module tao_anh_ai chưa được mount vào app.state.ai_image_service")
        ratio = str((plan.get("concept") or {}).get("aspect_ratio") or "16:9")
        base_prompt = str(scene.get("image_prompt") or scene.get("visual") or "").strip()
        style = self._style_for_plan(plan)
        size = self._image_size_for_ratio(ratio)
        lock = bool((plan.get("concept") or {}).get("character_lock", True)) and anchor is not None

        edit_source = continuity_anchor if continuity_anchor is not None else anchor
        use_edit = lock and edit_source is not None and callable(getattr(svc, "edit", None))

        img_steps = self._image_steps(quality, fast_mode)
        img_quality = self._image_gen_quality(quality, fast_mode)

        print(f"MASTER_REF={anchor.resolve() if anchor else 'None'}", flush=True)
        if continuity_anchor:
            print(f"PREVIOUS_LAST_FRAME={continuity_anchor.resolve()}", flush=True)
        else:
            print(f"PREVIOUS_LAST_FRAME=None (scene 1 or no continuity)", flush=True)
        print(f"SCENE_INPUT={out.resolve()}", flush=True)
        if fast_mode:
            print(f"FAST_MODE=ON image_retries={MAX_IMAGE_ATTEMPTS} steps={img_steps} img_quality={img_quality}", flush=True)

        attempts = []
        if cancel_event.is_set():
            raise AutoProduceCancelled("Đã dừng")
        repair = "" if not retry else " Quality repair: single scene, single camera angle, one character only, crisp face, symmetric eyes, natural mouth, correct anatomy, one coherent subject, sharp detail, no blur, no duplicate person, no character sheet, no multi-view, no lineup, no grid."
        prompt = base_prompt + self._reference_lock_prompt(plan) + repair

        current_strength = None
        if use_edit:
            if continuity_anchor is not None:
                strength = 0.30 if quality in {"high", "final"} else 0.34
                prompt = (prompt + " Same person, same face, same hair, same clothing, same sword, "
                          "same colors, same body type. Only change pose, camera angle, or environment. "
                          "Do NOT change identity, do NOT regenerate the character.")
            else:
                strength = 0.34 if quality in {"high", "final"} else 0.38
            # Reduce strength on retry
            if retry:
                strength = max(0.20, strength - 0.06)
                print(f"FACE_RETRY_REDUCED_STRENGTH: strength={strength:.2f}", flush=True)
            print(f"IMG2IMG_STRENGTH={strength:.2f}", flush=True)
            edit_kwargs = dict(
                strength=strength,
                cancel_event=cancel_event,
                progress=lambda p, s, d="": progress(p, f"Ảnh tham chiếu · {s}", d),
            )
            if img_steps is not None:
                edit_kwargs["steps"] = img_steps
            data = self._call_compat(svc.edit, edit_source, prompt, style, size, img_quality, **edit_kwargs)
        else:
            gen_kwargs = dict(
                cancel_event=cancel_event,
                progress=lambda p, s, d="": progress(p, f"Ảnh · {s}", d),
            )
            if img_steps is not None:
                gen_kwargs["steps"] = img_steps
            data = self._call_compat(svc.generate, prompt, style, size, img_quality, **gen_kwargs)

        if not isinstance(data, (bytes, bytearray)):
            raise RuntimeError("tao_anh_ai không trả image bytes hợp lệ")
        out.write_bytes(bytes(data))

        attempts.append({
            "attempt": 1,
            "reference_used": use_edit,
            "img2img_strength": current_strength,
        })

        # Return — validation happens in validate_image.
        # If validate_image fails, the caller (produce) decides whether to retry.
        return {
            "style": style, "size": size, "prompt": prompt,
            "path": str(out), "reference_used": use_edit,
            "attempts": attempts,
            "img2img_strength": current_strength,
        }

    # --- Stage 3: validate_image (SINGLE GATE — runs ONCE per image) ---
    def _validate_image(self, image: Path, plan: dict, *, anchor: Path | None = None,
                        continuity_anchor: Path | None = None, scene_id: int = 0,
                        fast_mode: bool = False) -> dict:
        """Single validation gate for a scene image. Runs ONCE.
        Checks: multi-panel, face/anatomy (subject-aware), identity continuity, technical QA.
        Does NOT re-run in generate_video.
        """
        # Multi-panel check
        is_multi, multi_reason = self._is_multi_panel_image(image)

        # Face anatomy gate (subject-aware)
        master_face = anchor if scene_id > 1 and anchor is not None else None
        face_result = self._face_anatomy_check(image, master_face=master_face)
        face_pass = face_result.get("pass", True)
        face_score = face_result.get("score", 0)
        subject_type = face_result.get("subject_type", "unknown")
        gate_mode = face_result.get("face_gate_mode", "unknown")
        ref_match = face_result.get("reference_match", "no_master")

        print(f"SUBJECT_TYPE={subject_type}", flush=True)
        print(f"FACE_GATE_MODE={gate_mode}", flush=True)
        print(f"REFERENCE_MATCH={ref_match}", flush=True)
        print(f"FACE_ANATOMY={'PASS' if face_pass else 'FAIL'}", flush=True)
        print(f"FACE_SCORE={face_score}", flush=True)

        # Identity continuity (scene 2+)
        identity_info = {}
        if continuity_anchor is not None and anchor is not None:
            sim = self._image_similarity(anchor, image)
            identity_info = sim
            print(f"IDENTITY_SCORE={sim.get('identity_score', 0)}", flush=True)
            print(f"OUTFIT_MATCH={sim.get('outfit_match', 0)}", flush=True)
            print(f"WEAPON_MATCH={sim.get('weapon_match', 0)}", flush=True)

        # Technical QA
        qa = image_quality(image)

        # Determine pass/fail
        passed = True
        reasons = []

        if is_multi:
            passed = False
            reasons.append(f"MULTI_PANEL: {multi_reason}")

        if not face_pass:
            passed = False
            reasons.append(f"FACE_ANATOMY_FAILED: score={face_score} reason={face_result.get('reason')}")

        # Identity check (relaxed in fast mode)
        if continuity_anchor is not None and anchor is not None:
            ident = identity_info.get("identity_score", 1.0)
            if fast_mode:
                min_ident = 0.40
            else:
                min_ident = 0.45
            if ident < min_ident:
                passed = False
                reasons.append(f"IDENTITY_DRIFT: score={ident}")

        if not qa.passed:
            passed = False
            reasons.append(f"IMAGE_QA_FAILED: {', '.join(qa.issues or [])}")

        return {
            "pass": passed,
            "reasons": reasons,
            "multi_panel": is_multi,
            "multi_panel_reason": multi_reason,
            "face": face_result,
            "identity": identity_info,
            "qa": qa.as_dict(),
        }

    # --- Stage 4: generate_video ---
    def _generate_video(self, image: Path, scene: dict, out: Path, cancel_event, progress,
                       quality: str, scene_id: int = 0) -> dict:
        """Generate video from image via SVD. NO retry loop. NO redundant face check.
        Atomic output: SVD output → copy to .tmp → rename to final.
        """
        svc = getattr(self.app.state, "video_ai_service", None)
        if svc is None:
            raise RuntimeError("Module tao_video_ai chưa được mount vào app.state.video_ai_service")

        # Validate input file exists and is readable
        if not image.is_file():
            raise RuntimeError(f"VIDEO_INPUT_MISSING: {image}")
        try:
            with Image.open(image) as im:
                im.load()
                img_w, img_h = im.size
        except Exception as exc:
            raise RuntimeError(f"VIDEO_INPUT_DECODE_FAILED: {image} — {exc}")

        print(f"VIDEO_INPUT_IMAGE={image.resolve()}", flush=True)
        print(f"INPUT_SIZE={img_w}x{img_h}", flush=True)
        print(f"SCENE_ID={scene_id}", flush=True)

        duration = max(2.0, min(6.0, parse_duration(scene.get("duration") or 3.0)))
        prompt = str(scene.get("video_prompt") or "")
        result = self._call_compat(
            svc.generate_image,
            image,
            prompt,
            quality=self._generator_quality(quality),
            duration=duration,
            fps=16,
            seed=int(scene.get("seed") or 0),
            cancel_event=cancel_event,
            progress=lambda p, s, d="": progress(p, f"Video · {s}", d),
        )
        if cancel_event.is_set():
            raise AutoProduceCancelled("Đã dừng")
        src = Path(svc.workspace.media_path(str(result["file"])))
        # Atomic copy: .tmp → rename
        self._atomic_copy(src, out)
        return dict(result, path=str(out), expected_duration=duration)

    # --- Stage 5: finalize_scene ---
    def _finalize_scene(self, raw_video: Path, norm_path: Path, ratio: str,
                        quality: str, scene: dict, expected_duration: float) -> dict:
        """Normalize to CFR 30fps and run video QA. Atomic output."""
        # _normalize_clip already does atomic write (.tmp → rename)
        self._normalize_clip(raw_video, norm_path, ratio, fps=30, quality=quality)
        w, h = self._ratio_size(ratio, quality)
        norm_qa = video_quality(
            norm_path,
            min_width=max(320, int(w * 0.75)),
            min_height=max(320, int(h * 0.75)),
            expected_duration=expected_duration,
        )
        print(f"CFR_QA · fps={norm_qa.checks.get('fps')} · frames={norm_qa.checks.get('frame_count')} · duration={norm_qa.checks.get('duration')}s", flush=True)
        return {"normalized": str(norm_path), "qa": norm_qa.as_dict(), "passed": norm_qa.passed}

    # ==================================================================
    # MAIN ORCHESTRATOR — linear, no nested retries
    # ==================================================================

    def produce(self, plan: dict, folder: Path, *, quality="balanced",
               cancel_event: threading.Event, progress, fast_mode: bool = False):
        mode_label = "FAST MODE" if fast_mode else "STANDARD"
        progress(1, f"LINEAR PIPELINE V7.0 {mode_label}", "1 scene = 1 image + tối đa 1 retry + 1 video + 1 finalize")
        scenes = plan.get("scenes") or []
        if not scenes:
            raise ValueError("Plan không có scene")
        if quality not in {"draft", "balanced", "high", "final"}:
            raise ValueError("quality phải là draft/balanced/high/final")
        ratio = str((plan.get("concept") or {}).get("aspect_ratio") or "16:9")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "scenes").mkdir(exist_ok=True)
        (folder / "qa").mkdir(exist_ok=True)
        self._write_srt(plan, folder / "subtitles.srt")
        manifest = {
            "version": "7.0.0-linear-pipeline" + ("-fast" if fast_mode else ""),
            "quality": quality,
            "fast_mode": fast_mode,
            "max_image_attempts": MAX_IMAGE_ATTEMPTS,
            "character_lock": bool((plan.get("concept") or {}).get("character_lock", True)),
            "character_reference_id": (plan.get("concept") or {}).get("character_reference_id"),
            "scenes": [], "started_at": time.time(), "warnings": [],
        }

        # Audio prep in parallel (CPU-only, no GPU contention)
        duration = parse_duration((plan.get("concept") or {}).get("duration_seconds") or sum(parse_duration(s.get("duration") or 0) for s in scenes))
        audio_result = {"voice": None, "music": None, "error": None}
        def _prepare_audio():
            try:
                audio_result["voice"] = self._build_voice_track(plan, folder, duration)
                audio_result["music"] = self._pick_music(plan)
            except Exception as exc:
                audio_result["error"] = str(exc)
        audio_thread = threading.Thread(target=_prepare_audio, daemon=True, name="aivf-audio-prep")
        audio_thread.start()

        # Stage 1: prepare_reference (master anchor)
        anchor = self._prepare_reference(plan, folder, cancel_event, progress, quality)
        if anchor:
            manifest["character_anchor"] = str(anchor)
        else:
            manifest["character_anchor"] = None

        # Scene loop — LINEAR, no nested retries
        normalized = []
        continuity_frame = None
        total = len(scenes)

        for idx, scene in enumerate(scenes, 1):
            if cancel_event.is_set():
                raise AutoProduceCancelled("Đã dừng")
            base = 8 + int((idx - 1) / total * 70)
            span = max(1, int(70 / total))
            image_path = folder / "scenes" / f"scene_{idx:02d}.png"
            norm_path = folder / "scenes" / f"scene_{idx:02d}_final.mp4"

            # Skip already-completed scenes (resume support)
            if norm_path.is_file():
                w_chk, h_chk = self._ratio_size(ratio, quality)
                existing_qa = video_quality(norm_path,
                    min_width=max(320, int(w_chk * 0.75)),
                    min_height=max(320, int(h_chk * 0.75)),
                    expected_duration=parse_duration(scene.get("duration") or 3))
                if existing_qa.passed and image_path.is_file():
                    print(f"SCENE_SKIP_ALREADY_PASS: scene={idx}", flush=True)
                    if idx < total:
                        next_frame = folder / "scenes" / f"scene_{idx:02d}_lastframe.png"
                        if not next_frame.is_file():
                            self._extract_last_frame(norm_path, next_frame)
                        continuity_frame = next_frame if next_frame.is_file() else image_path
                    normalized.append(norm_path)
                    manifest["scenes"].append({"id": scene.get("id", idx), "skipped": True, "normalized": str(norm_path)})
                    continue

            if idx == 1:
                progress(base + 1, f"Scene {idx}/{total}", "Tạo ảnh + MASTER CHARACTER REFERENCE")
            else:
                progress(base + 1, f"Scene {idx}/{total}", f"Tạo ảnh từ last frame scene {idx-1} (continuity lock)")

            # Stage 2: generate_image (attempt 1)
            img_meta = self._generate_image(
                scene, plan, image_path, cancel_event,
                lambda p, s, d="": progress(base + max(1, int(p / 100 * span * 0.38)), f"Scene {idx}/{total} · {s}", d),
                quality=quality, anchor=anchor,
                continuity_anchor=continuity_frame, scene_id=idx,
                fast_mode=fast_mode,
            )

            # Stage 3: validate_image (SINGLE GATE — runs ONCE)
            validation = self._validate_image(
                image_path, plan,
                anchor=anchor, continuity_anchor=continuity_frame,
                scene_id=idx, fast_mode=fast_mode,
            )

            # If validation fails on attempt 1, allow 1 retry (MAX_IMAGE_ATTEMPTS = 2)
            if not validation["pass"]:
                print(f"SCENE_IMAGE_VALIDATION_FAILED: scene={idx} reasons={validation['reasons']}", flush=True)
                if not validation.get("face", {}).get("pass", True):
                    # Face anatomy failed — retry with reduced strength
                    img_meta = self._generate_image(
                        scene, plan, image_path, cancel_event,
                        lambda p, s, d="": progress(base + max(1, int(p / 100 * span * 0.38)), f"Scene {idx}/{total} · RETRY · {s}", d),
                        quality=quality, anchor=anchor,
                        continuity_anchor=continuity_frame, scene_id=idx,
                        fast_mode=fast_mode, retry=True,
                    )
                    validation = self._validate_image(
                        image_path, plan,
                        anchor=anchor, continuity_anchor=continuity_frame,
                        scene_id=idx, fast_mode=fast_mode,
                    )
                    if not validation["pass"]:
                        raise RuntimeError(
                            f"IMAGE_VALIDATION_FAILED: scene={idx} reasons={validation['reasons']}. "
                            "Image rejected before video diffusion."
                        )
                else:
                    raise RuntimeError(
                        f"IMAGE_VALIDATION_FAILED: scene={idx} reasons={validation['reasons']}"
                    )

            print(f"IMAGE_PASS: scene={idx}", flush=True)

            # Stage 4: generate_video (NO retry, NO redundant face check)
            progress(base + int(span * 0.42), f"Scene {idx}/{total}", "Tạo chuyển động (SVD)")
            raw_video = folder / "scenes" / f"scene_{idx:02d}_raw.mp4"
            vid_meta = self._generate_video(
                image_path, scene, raw_video, cancel_event,
                lambda p, s, d="": progress(base + int(span * 0.42) + max(1, int(p / 100 * span * 0.42)), f"Scene {idx}/{total} · {s}", d),
                quality, scene_id=idx,
            )

            # Stage 5: finalize_scene (normalize + QA)
            progress(base + int(span * 0.82), f"Scene {idx}/{total}", "Chuẩn hóa CFR 30fps")
            finalize = self._finalize_scene(
                raw_video, norm_path, ratio, quality, scene,
                parse_duration(vid_meta.get("expected_duration") or scene.get("duration") or 3),
            )
            if not finalize["passed"]:
                raise RuntimeError("VIDEO_QA_FAILED: " + ", ".join(finalize["qa"].get("issues") or []))

            # Extract last frame for next scene's continuity
            if idx < total:
                next_frame = folder / "scenes" / f"scene_{idx:02d}_lastframe.png"
                if self._extract_last_frame(norm_path, next_frame):
                    continuity_frame = next_frame
                    print(f"CONTINUITY_FRAME_EXTRACTED: scene={idx} -> {next_frame.resolve()}", flush=True)
                else:
                    continuity_frame = image_path
                    print(f"CONTINUITY_FRAME_FALLBACK: using scene image {image_path.name}", flush=True)

            normalized.append(norm_path)
            manifest["scenes"].append({
                "id": scene.get("id", idx),
                "image": img_meta,
                "video": vid_meta,
                "validation": validation,
                "finalize": finalize,
                "normalized": str(norm_path),
                "continuity_frame": str(continuity_frame) if continuity_frame else None,
            })

        # Concat all scenes
        progress(82, "Ghép cảnh", "Nối các shot đã PASS QA")
        visual = self._concat(normalized, folder / "visual_master.mp4")
        progress(87, "Voice + Nhạc", "Đang nhận kết quả audio đã chuẩn bị song song")
        audio_thread.join(timeout=180)
        voice = audio_result.get("voice")
        music = audio_result.get("music")
        if audio_result.get("error"):
            manifest["warnings"].append("AUDIO_PREP_WARNING: " + str(audio_result["error"]))
        if voice is None:
            manifest["warnings"].append("VOICE_SKIPPED: Windows SAPI không khả dụng hoặc không tạo được voice; subtitles vẫn được xuất.")
        if music is None:
            manifest["warnings"].append("MUSIC_SKIPPED: không tìm thấy track local phù hợp.")
        progress(93, "Master", "Mix voice/nhạc bằng stream-copy video")
        mixed = self._final_mix(visual, voice, music, folder / "MIXED_VIDEO.mp4", duration)
        progress(97, "Final Quality", "Final master encode")
        final = folder / "FINAL_VIDEO.mp4"
        if quality == "high":
            shutil.copy2(mixed, final)
        else:
            self._final_master(mixed, final, ratio, quality)
        w, h = self._ratio_size(ratio, quality)
        final_qa = video_quality(final, min_width=max(640, int(w * 0.75)), min_height=max(360, int(h * 0.75)), expected_duration=duration)
        if not final_qa.passed:
            raise RuntimeError("FINAL_VIDEO_QA_FAILED: " + ", ".join(final_qa.issues))
        manifest.update({
            "finished_at": time.time(), "final_video": str(final), "visual_master": str(visual),
            "mixed_video": str(mixed), "final_qa": final_qa.as_dict(),
            "voice": str(voice) if voice else None, "music": str(music) if music else None,
            "subtitles": str(folder / "subtitles.srt"), "nvenc_available": self._has_nvenc(),
            "output_target": {"width": w, "height": h, "fps": 30},
            "pipeline": "linear_v7",
            "speed_optimizations": {
                "audio_parallel": True,
                "high_skip_redundant_final_encode": quality == "high",
                "nvenc": self._has_nvenc(),
                "fast_mode": fast_mode,
                "image_steps": self._image_steps(quality, fast_mode),
                "max_image_attempts": MAX_IMAGE_ATTEMPTS,
                "skip_passed_scenes": True,
                "atomic_file_output": True,
            },
        })
        (folder / "production_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        progress(100, "Hoàn tất", str(final))
        return manifest


class AutoProduceJobManager:
    def __init__(self, app, root: Path):
        self.app = app
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, threading.Event] = {}

    def start(self, plan: dict, quality="balanced", fast_mode: bool = False) -> str:
        jid = uuid4().hex
        folder = self.root / f"produce_{time.strftime('%Y%m%d_%H%M%S')}_{jid[:8]}"
        ev = threading.Event()
        now = time.time()
        with self._lock:
            self._events[jid] = ev
            scene_count = len(plan.get("scenes") or [])
            base_per_scene = {"draft": 180, "balanced": 360, "high": 600, "final": 780}.get(quality, 360)
            rough_per_scene = int(base_per_scene * 0.6) if fast_mode else base_per_scene
            rough_total = max(120, scene_count * rough_per_scene + 120)
            self._jobs[jid] = {"job_id": jid, "status": "queued", "progress": 1, "stage": "Đang xếp hàng", "detail": "", "folder": str(folder), "fast_mode": fast_mode, "result": None, "error": None, "created_at": now, "started_at": None, "updated_at": now, "elapsed_seconds": 0, "eta_seconds": rough_total, "eta_source": "initial_estimate", "stage_started_at": now}
        producer = AutoProducer(self.app, self.root)
        def update(p, stage, detail=""):
            with self._lock:
                if jid in self._jobs:
                    job = self._jobs[jid]
                    now2 = time.time()
                    if not job.get("started_at"):
                        job["started_at"] = now2
                    progress_i = max(1, min(100, int(p)))
                    elapsed = max(0.0, now2 - float(job.get("started_at") or now2))
                    prev_stage = job.get("stage")
                    if stage != prev_stage:
                        job["stage_started_at"] = now2
                    eta = job.get("eta_seconds")
                    if progress_i >= 3 and elapsed >= 10:
                        rate = (progress_i - 1) / elapsed
                        if rate > 0:
                            raw_eta = max(0.0, (100 - progress_i) / rate)
                            old_eta = float(eta or raw_eta)
                            eta = raw_eta if job.get("eta_source") == "initial_estimate" else (old_eta * 0.65 + raw_eta * 0.35)
                            job["eta_source"] = "live"
                    job.update(status="running", progress=progress_i, stage=stage, detail=detail, updated_at=now2, elapsed_seconds=int(elapsed), eta_seconds=int(max(0, eta or 0)), stage_elapsed_seconds=int(max(0, now2-float(job.get("stage_started_at") or now2))))
        def run():
            try:
                with self._lock:
                    if jid in self._jobs:
                        self._jobs[jid]["started_at"] = time.time()
                        self._jobs[jid]["stage_started_at"] = self._jobs[jid]["started_at"]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "project.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
                result = producer.produce(plan, folder, quality=quality, cancel_event=ev, progress=update, fast_mode=fast_mode)
                with self._lock:
                    now3=time.time(); started=float(self._jobs[jid].get("started_at") or now3)
                    self._jobs[jid].update(status="done", progress=100, stage="Hoàn tất", detail="FINAL_VIDEO.mp4 đã PASS Quality Gate", result=result, updated_at=now3, elapsed_seconds=int(now3-started), eta_seconds=0, stage_elapsed_seconds=0)
            except AutoProduceCancelled as exc:
                with self._lock:
                    self._jobs[jid].update(status="cancelled", stage="Đã dừng", detail=str(exc), updated_at=time.time())
            except Exception as exc:
                with self._lock:
                    self._jobs[jid].update(status="error", stage="Lỗi LINEAR PIPELINE AUTO PRODUCE", detail=str(exc), error=str(exc), updated_at=time.time())
        threading.Thread(target=run, daemon=True, name=f"aivf-auto-produce-{jid[:8]}").start()
        return jid

    def get(self, jid: str) -> dict:
        with self._lock:
            if jid not in self._jobs:
                raise KeyError(jid)
            return dict(self._jobs[jid])

    def cancel(self, jid: str) -> bool:
        with self._lock:
            ev = self._events.get(jid)
            job = self._jobs.get(jid)
            if not ev or not job or job.get("status") in {"done","error","cancelled"}:
                return False
            ev.set()
            job.update(stage="Đang dừng", detail="Sẽ dừng ở bước an toàn gần nhất", updated_at=time.time())
            return True
