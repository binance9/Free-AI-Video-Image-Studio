from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
import io

from PIL import Image

from .image_runtime import StandaloneLocalImageService, SafetyBlockedOutput
from .character_profile import CharacterProfile
from .spec_parser import parse_character_spec
from .prompt_lock import build_locked_prompt
from .attribute_lock import AttributeLock
from .preview_validator import validate_candidate
from .repair_planner import plan_repairs
from .export_gate import export_if_passed
from .job_report import write_report
from .consistency import histogram_similarity
from .sprite_export import export_sheet
from .direction_builder import build_pose_hint
from .reference_lock import ReferenceLibrary
from .reference_similarity import clip_reference_similarity
from .from_reference import normalize_reference_bytes
from .output_guard import build_repair_negative_prompt, build_repair_prompt
from .material_recolor import recolor_materials
from .preserve_refine import refine_reference_image
from .quality_gate import evaluate_anchor
from .operation_gate import detect_operation, target_palette_score, build_recolor_gate




def _is_recolor_request(prompt: str) -> bool:
    low = (prompt or "").lower()
    triggers = (
        "change the armor color", "change armor color", "change the armor colors", "change armor colors",
        "change the cape", "change cape", "recolor", "re-colour", "recoloring", "đổi màu", "đổi màu sắc",
        "burgundy", "crimson", "maroon",
    )
    return any(t in low for t in triggers)


def _is_preserve_request(prompt: str) -> bool:
    low = (prompt or "").lower()
    change_triggers = (
        "change ", "replace ", "turn into", "convert to", "recolor", "re-colour",
        "đổi ", "thay ", "burgundy", "crimson", "maroon",
    )
    if any(t in low for t in change_triggers):
        return False
    preserve_triggers = (
        "clean and refine", "clean & refine", "refine the reference", "improve sharpness",
        "improve detail", "keep the same design", "same colors", "same proportions",
        "keep everything the same", "giữ nguyên", "làm nét", "tăng độ nét",
    )
    return any(t in low for t in preserve_triggers)

def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _render_retry_directive(exc: Exception) -> list[str]:
    msg = str(exc).lower()
    if "safety_checker_blocked" in msg:
        return [
            "FULLY CLOTHED NON-SUGGESTIVE FANTASY GAME CHARACTER",
            "NEUTRAL STANDING POSE, NO EXPOSED BODY, NO SEXUALIZED PRESENTATION",
            "BRIGHT LIGHT GRAY BACKGROUND, CLEAR SAFE GAME ASSET",
        ]
    if "blank_or_black_image_output" in msg or "no_images" in msg:
        return [
            "BRIGHT LIGHT GRAY BACKGROUND, CLEAR VISIBLE CHARACTER, NO BLACK FRAME",
            "FULL BODY CENTERED AND WELL LIT",
        ]
    return []


class Character2DService:
    """V11 hard-lock pipeline.

    A candidate may be generated many times, but it is not promoted to
    anchor.png / sheet.png until the hard gate passes.
    """

    def __init__(self, image_service: StandaloneLocalImageService | None = None, root: str | Path | None = None):
        project_root = _project_root()
        model_dir = project_root / "data" / "models" / "image"
        validator_dir = project_root / "data" / "models" / "validator"
        model_dir.mkdir(parents=True, exist_ok=True)
        self.image_service = image_service or StandaloneLocalImageService(None, model_dir)
        self.attribute_lock = AttributeLock(validator_dir)
        self.reference_library = ReferenceLibrary()
        self.root = Path(root or (project_root / "data" / "character_2d_addon")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _save_png_bytes(image_bytes: bytes, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as im:
            im.save(path, format="PNG")
        return path

    def parse_spec(self, prompt: str, preset: str = "compact_game") -> dict:
        spec = parse_character_spec(prompt)
        spec.render_preset = preset
        return spec.to_dict()

    def _generate_locked_anchor(self, profile: CharacterProfile, *, size: str, style: str, quality: str,
                                min_score: int, max_attempts: int, job_dir: Path, preset: str = "compact_game") -> dict:
        spec = parse_character_spec(" ".join(profile.notes or []))
        spec.render_preset = preset
        rejected_dir = job_dir / "rejected"
        history = []
        repair_directives: list[str] = []
        best = None

        reference = self.reference_library.choose(spec)
        for attempt in range(1, max(1, int(max_attempts)) + 1):
            prompt, negative = build_locked_prompt(spec, repair_directives)
            if repair_directives:
                prompt = build_repair_prompt(prompt)
                negative = build_repair_negative_prompt(negative)
            if reference.enabled and reference.path:
                # V12.2 strict mode: the approved reference is the source of truth.
                # Keep denoising low for an exact spec match; retries add only a tiny
                # amount of freedom instead of destroying identity/weapon class.
                if reference.strict:
                    strength = min(0.34, reference.strength + (attempt - 1) * 0.03)
                    ref_instruction = (
                        "PRESERVE THE EXACT SAME MALE IDENTITY, CHIBI BODY PROPORTIONS, BLUE ARMOR LAYOUT, "
                        "PURPLE SASH, LONG DARK HAIR, AND EXACTLY ONE BLADED SWORD FROM THE REFERENCE. "
                        "DO NOT CHANGE GENDER. DO NOT TURN THE SWORD INTO A GUN, CAMERA, RIFLE OR OTHER OBJECT. "
                        "ONLY CLEAN AND REFINE THE APPROVED CHARACTER. "
                    )
                else:
                    strength = min(0.46, reference.strength + (attempt - 1) * 0.03)
                    ref_instruction = (
                        "USE THE REFERENCE AS THE MAIN CHARACTER STRUCTURE. PRESERVE IDENTITY, BODY PROPORTIONS, "
                        "CAMERA FRAMING AND WEAPON FAMILY WHILE APPLYING THE REQUESTED SPEC. "
                    )
                try:
                    data = self.image_service.edit(
                        reference.path, f"{ref_instruction}{prompt}",
                        style, size, quality, strength=strength, negative_prompt=negative,
                    )
                except Exception as exc:
                    directives = _render_retry_directive(exc)
                    history.append({
                        "attempt": attempt, "candidate": None, "render_error": str(exc),
                        "repair_directives": directives, "reference": self.reference_library.info(spec),
                    })
                    if directives:
                        repair_directives = directives
                        continue
                    raise
            else:
                try:
                    data = self.image_service.generate(prompt, style, size, quality, negative_prompt=negative)
                except Exception as exc:
                    directives = _render_retry_directive(exc)
                    history.append({"attempt": attempt, "candidate": None, "render_error": str(exc), "repair_directives": directives})
                    if directives:
                        repair_directives = directives
                        continue
                    raise
            candidate = self._save_png_bytes(data, rejected_dir / f"candidate_{attempt:02d}.png")
            validation = validate_candidate(candidate, spec, self.attribute_lock, min_score)
            reference_similarity = None
            if reference.enabled and reference.path and reference.strict:
                reference_similarity = clip_reference_similarity(self.attribute_lock, candidate, reference.path)
                if reference_similarity.get("ok") is False:
                    validation["reference_similarity"] = reference_similarity
                    validation["gate"]["accepted"] = False
                    blockers = list(validation["gate"].get("blockers", []))
                    if "reference_drift" not in blockers:
                        blockers.append("reference_drift")
                    validation["gate"]["blockers"] = blockers
                else:
                    validation["reference_similarity"] = reference_similarity
            row = {
                "attempt": attempt,
                "candidate": str(candidate),
                "prompt": prompt,
                "validation": validation,
                "reference": self.reference_library.info(spec),
            }
            history.append(row)
            score = float(validation["gate"].get("quality_score", 0))
            if best is None or score > best[0]:
                best = (score, candidate, validation)
            if validation["gate"].get("accepted"):
                return {"accepted": True, "candidate": candidate, "validation": validation,
                        "history": history, "spec": spec}
            blockers = validation["gate"].get("blockers", [])
            repair_directives = plan_repairs(blockers, spec)

        return {"accepted": False, "candidate": best[1] if best else None,
                "validation": best[2] if best else None, "history": history, "spec": spec}

    def create_anchor(self, profile: CharacterProfile, *, size: str = "1024x1024", style: str = "fantasy",
                      quality: str = "high", mode: str = "final", max_repairs: int = 2,
                      min_score: int = 72, preset: str = "compact_game") -> dict:
        job_dir = self.root / f"job_{uuid4().hex[:12]}"
        job_dir.mkdir(parents=True, exist_ok=True)
        render_quality = "fast" if mode == "preview" else quality
        attempts = 3 if mode == "preview" else max(3, int(max_repairs) + 2)

        locked = self._generate_locked_anchor(
            profile, size=size, style=style, quality=render_quality,
            min_score=min_score, max_attempts=attempts, job_dir=job_dir, preset=preset,
        )
        gate = locked.get("validation", {}).get("gate", {}) if locked.get("validation") else {}
        exported = None
        if locked.get("accepted") and locked.get("candidate"):
            exported = export_if_passed(
                locked["candidate"], job_dir / ("preview.png" if mode == "preview" else "anchor.png"), gate
            )

        result = {
            "version": "1.3.1",
            "mode": mode,
            "status": "accepted" if exported else "rejected",
            "accepted": bool(exported),
            "spec": locked["spec"].to_dict(),
            "anchor": exported,
            "best_rejected_candidate": None if exported else (
                str(locked["candidate"])
                if locked.get("candidate") and locked.get("validation", {}).get("base", {}).get("image", {}).get("ok")
                else None
            ),
            "export_gate": gate,
            "attempts": locked["history"],
            "ready_for_directions": bool(exported),
            "size": size,
            "style": style,
            "quality": render_quality,
            "preset": preset,
            "reference_lock": self.reference_library.info(locked["spec"]),
        }
        write_report(job_dir / "manifest.json", result)
        return result


    def create_from_reference(self, reference_bytes: bytes, filename: str, prompt: str, *,
                              size: str = "1024x1024", style: str = "fantasy", quality: str = "medium",
                              min_score: int = 70, max_repairs: int = 3, strength: float = 0.28,
                              preset: str = "compact_game") -> dict:
        """Create a locked character from a user-supplied reference image.

        The source image is normalized without cropping, then reused for every retry.
        This prevents retries from drifting progressively away from the user's reference.
        """
        job_dir = self.root / f"job_ref_{uuid4().hex[:12]}"
        job_dir.mkdir(parents=True, exist_ok=True)
        source = normalize_reference_bytes(reference_bytes, filename, job_dir / "reference_input.png")
        spec = parse_character_spec(prompt)
        spec.render_preset = preset
        rejected_dir = job_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        history = []
        repair_directives: list[str] = []
        best = None
        requested_strength = max(0.16, min(0.42, float(strength)))
        operation = detect_operation(prompt)
        preserve_mode = operation == "preserve-refine"

        # V12.9: a pure clean/refine request must NOT re-diffuse the character.
        # The uploaded image is the source of truth, so gently sharpen it and
        # validate only structural image quality. This prevents needless drift,
        # black outputs and false semantic rejects for unspecified/null fields.
        if preserve_mode:
            refined_info = refine_reference_image(source, job_dir / "reference_refined.png")
            candidate = Path(refined_info["output"])
            base_gate = evaluate_anchor(candidate, min_score=max(58, min(int(min_score), 68)))
            similarity = clip_reference_similarity(self.attribute_lock, candidate, source, threshold=0.90)
            blockers = list(base_gate.get("issues", [])) if not base_gate.get("passed") else []
            if similarity.get("ok") is False and "reference_drift" not in blockers:
                blockers.append("reference_drift")
            gate = {
                "accepted": bool(base_gate.get("passed") and similarity.get("ok") is not False),
                "blockers": blockers,
                "uncertain": [],
                "quality_score": base_gate.get("quality_score", 0),
                "minimum_score": max(58, min(int(min_score), 68)),
                "strict_attribute_gate": False,
                "preserve_reference_is_source_of_truth": True,
            }
            history.append({
                "attempt": 1, "candidate": str(candidate), "strength": 0.0,
                "validation": {"base": base_gate, "reference_similarity": similarity, "gate": gate},
                "preserve_refine": refined_info,
            })
            exported = export_if_passed(candidate, job_dir / "reference_result.png", gate)
            result = {
                "version": "1.3.1", "mode": "from-reference",
                "operation": "preserve-refine",
                "status": "accepted" if exported else "rejected",
                "accepted": bool(exported), "spec": spec.to_dict(),
                "reference": str(source), "image": exported, "export_gate": gate,
                "attempts": history, "strength": 0.0,
                "requested_strength": requested_strength, "auto_recolor": False,
                "preserve_mode": True, "diffusion_used": False, "preset": preset,
                "best_rejected_candidate": None if exported else (str(candidate) if base_gate.get("image", {}).get("ok") else None),
            }
            write_report(job_dir / "manifest.json", result)
            return result
        recolor_mode = operation == "recolor-reference" and bool(spec.armor_primary or getattr(spec, "cape_color", None) or spec.accent_color)
        # Color changes need more denoising than identity-preserving cleanup.
        # Raise only the effective strength; geometry/weapon are still locked by prompt + validators.
        base_strength = max(requested_strength, 0.38) if recolor_mode else requested_strength

        edit_source = source
        recolor_prefill = None
        if recolor_mode:
            recolor_prefill = recolor_materials(source, job_dir / "reference_recolored.png", spec)
            if recolor_prefill.get("ok"):
                edit_source = Path(recolor_prefill["output"])
                # Palette is already changed deterministically. Diffusion only refines details.
                base_strength = max(0.18, min(0.24, requested_strength))

        total_attempts = 1 + max(0, int(max_repairs))
        for attempt in range(1, total_attempts + 1):
            locked_prompt, negative = build_locked_prompt(spec, repair_directives)
            if repair_directives:
                locked_prompt = build_repair_prompt(locked_prompt)
                negative = build_repair_negative_prompt(negative)
            preserve = (
                "USE THE UPLOADED REFERENCE AS THE PRIMARY VISUAL SOURCE. "
                "PRESERVE THE SAME CHIBI BODY PROPORTIONS, FACE STYLE, CAMERA FRAMING, POSE FAMILY, "
                "AND OVERALL SILHOUETTE. CHANGE ONLY ATTRIBUTES EXPLICITLY REQUESTED IN THE PROMPT. "
                "DO NOT INVENT A NEW WEAPON FAMILY OR EXTRA EQUIPMENT. "
            )
            if recolor_mode:
                preserve += (
                    "THIS IS A MATERIAL RECOLOR EDIT. PRESERVE SHAPE, FACE, HAIR STYLE, BOW/WEAPON GEOMETRY AND POSE, "
                    "BUT RECOLOR THE REQUESTED ARMOR/CLOTH/CAPE MATERIALS STRONGLY AND VISIBLY. "
                    "THE OLD SOURCE COLORS MUST NOT DOMINATE THE EDITED GARMENTS. "
                )
            try_strength = min(0.46, base_strength + (attempt - 1) * 0.03)
            try:
                data = self.image_service.edit(
                    edit_source, f"{preserve}{locked_prompt}", style, size, quality,
                    strength=try_strength, negative_prompt=negative,
                )
            except Exception as exc:
                directives = _render_retry_directive(exc)
                history.append({
                    "attempt": attempt, "candidate": None, "strength": round(try_strength, 3),
                    "render_error": str(exc), "repair_directives": directives,
                })
                if directives:
                    repair_directives = directives
                    continue
                raise
            candidate = self._save_png_bytes(data, rejected_dir / f"candidate_{attempt:02d}.png")
            validation = validate_candidate(candidate, spec, self.attribute_lock, min_score)
            similarity = clip_reference_similarity(self.attribute_lock, candidate, source, threshold=0.54 if recolor_mode else 0.74)
            validation["reference_similarity"] = similarity
            if recolor_mode:
                palette = target_palette_score(candidate, spec)
                validation["target_palette"] = palette
                validation["gate"] = build_recolor_gate(validation, similarity, palette, min_score)
            elif similarity.get("ok") is False:
                validation["gate"]["accepted"] = False
                blockers = list(validation["gate"].get("blockers", []))
                if "reference_drift" not in blockers:
                    blockers.append("reference_drift")
                validation["gate"]["blockers"] = blockers

            row = {
                "attempt": attempt, "candidate": str(candidate), "strength": round(try_strength, 3),
                "validation": validation, "recolor_prefill": recolor_prefill,
            }
            history.append(row)
            score = float(validation["gate"].get("quality_score", 0))
            if best is None or score > best[0]:
                best = (score, candidate, validation)
            if validation["gate"].get("accepted"):
                exported = export_if_passed(candidate, job_dir / "reference_result.png", validation["gate"])
                result = {
                    "version": "1.3.1", "mode": "from-reference", "operation": operation, "status": "accepted",
                    "accepted": bool(exported), "spec": spec.to_dict(),
                    "reference": str(source), "image": exported, "export_gate": validation["gate"],
                    "attempts": history, "strength": base_strength, "requested_strength": requested_strength, "auto_recolor": recolor_mode, "preserve_mode": False, "diffusion_used": True,
                    "recolor_prefill": recolor_prefill, "preset": preset,
                }
                write_report(job_dir / "manifest.json", result)
                return result

            blockers = validation["gate"].get("blockers", [])
            repair_directives = plan_repairs(blockers, spec)
            if "reference_drift" in blockers:
                repair_directives.append("PRESERVE THE UPLOADED REFERENCE MORE CLOSELY; DO NOT REDESIGN THE CHARACTER")

        result = {
            "version": "1.3.1", "mode": "from-reference", "operation": operation, "status": "rejected", "accepted": False,
            "spec": spec.to_dict(), "reference": str(source), "image": None,
            "best_rejected_candidate": (
                str(best[1])
                if best and best[2].get("base", {}).get("image", {}).get("ok")
                else None
            ),
            "export_gate": best[2]["gate"] if best else {}, "attempts": history,
            "strength": base_strength, "requested_strength": requested_strength, "auto_recolor": recolor_mode, "preserve_mode": False, "diffusion_used": True,
            "recolor_prefill": recolor_prefill, "preset": preset,
        }
        write_report(job_dir / "manifest.json", result)
        return result

    def _frame_prompt(self, spec, direction: str, action: str, frame_index: int, frames: int, repair: list[str] | None = None):
        base, negative = build_locked_prompt(spec, repair)
        pose = build_pose_hint(direction, action, frame_index, frames)
        return f"{base}. SAME EXACT CHARACTER AND EQUIPMENT. {pose}. FULL BODY GAME SPRITE", negative

    def create_action_sheet(self, profile: CharacterProfile, *, directions: list[str], action: str,
                            frames: int = 4, size: str = "1024x1024", style: str = "fantasy",
                            quality: str = "high", min_score: int = 72, preset: str = "compact_game") -> dict:
        anchor_info = self.create_anchor(profile, size=size, style=style, quality=quality,
                                         mode="final", max_repairs=3, min_score=min_score, preset=preset)
        if not anchor_info.get("accepted") or not anchor_info.get("anchor"):
            raise ValueError("V11 Hard Lock: anchor bị reject; không sinh sheet và không xuất ảnh final.")

        spec = parse_character_spec(" ".join(profile.notes or []))
        spec.render_preset = preset
        anchor_path = Path(anchor_info["anchor"])
        job_dir = anchor_path.parent
        rejected_dir = job_dir / "rejected_frames"
        accepted_paths, labels, metrics = [], [], []

        for direction in directions:
            for frame_index in range(frames):
                accepted = None
                repair: list[str] = []
                frame_history = []
                for attempt in range(1, 3):
                    prompt, negative = self._frame_prompt(spec, direction, action, frame_index, frames, repair)
                    edited = self.image_service.edit(anchor_path, prompt, style, size,
                                                     "medium" if quality == "high" else quality,
                                                     strength=0.38, negative_prompt=negative)
                    candidate = self._save_png_bytes(
                        edited, rejected_dir / f"{action}_{direction}_{frame_index:02d}_try{attempt}.png"
                    )
                    validation = validate_candidate(candidate, spec, self.attribute_lock, max(58, min_score - 10))
                    similarity = histogram_similarity(anchor_path, candidate)
                    frame_history.append({"attempt": attempt, "candidate": str(candidate),
                                          "validation": validation, "similarity_to_anchor": similarity})
                    if validation["gate"].get("accepted") and similarity >= 0.42:
                        out = job_dir / "accepted_frames" / f"{action}_{direction}_{frame_index:02d}.png"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with Image.open(candidate) as im:
                            im.save(out, "PNG")
                        accepted = out
                        break
                    blockers = validation["gate"].get("blockers", [])
                    if similarity < 0.42:
                        blockers = list(blockers) + ["preserve_identity"]
                    repair = plan_repairs(blockers, spec)
                    if "preserve_identity" in blockers:
                        repair.append("PRESERVE SAME FACE, HAIR, ARMOR AND BODY PROPORTIONS AS ANCHOR")
                metrics.append({"direction": direction, "frame": frame_index,
                                "accepted": bool(accepted), "history": frame_history})
                if not accepted:
                    result = {"status": "rejected", "accepted": False, "anchor": str(anchor_path),
                              "reason": f"frame_failed:{direction}:{frame_index}", "frames": metrics}
                    write_report(job_dir / f"report_{action}.json", result)
                    return result
                accepted_paths.append(accepted)
                labels.append(f"{action}:{direction}:{frame_index}")

        sheet_info = export_sheet(
            accepted_paths, max(1, frames), job_dir / f"sheet_{action}.png",
            job_dir / f"sheet_{action}.json", labels
        )
        result = {"status": "accepted", "accepted": True, "job_dir": str(job_dir),
                  "anchor": str(anchor_path), "sheet": sheet_info, "frames": metrics,
                  "spec": spec.to_dict(), "action": action, "directions": directions}
        write_report(job_dir / f"report_{action}.json", result)
        return result
