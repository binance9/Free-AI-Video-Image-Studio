from __future__ import annotations

import json
import math
import re
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .module_router import route_task, MODULE_CONTRACTS
from .memory_store import DirectorMemoryStore


@dataclass
class DirectorConfig:
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ai_timeout: int = 90


class AIVideoDirectorService:
    """Beginner-first pre-production director.

    The service converts one plain-language idea into a deterministic production
    package: concept, script, storyboard, shots, image/video prompts, camera,
    voice, captions, music and edit instructions. It can use a local Ollama model
    when available, and always has a no-network fallback.
    """

    def __init__(self, root: Path, config: DirectorConfig | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = config or DirectorConfig()
        self.memory = DirectorMemoryStore(self.root / "memory")

    @staticmethod
    def _slug(text: str) -> str:
        x = re.sub(r"[^a-zA-Z0-9_-]+", "-", (text or "video").strip()).strip("-")
        return (x[:48] or "video").lower()

    def _ollama_json(self, system: str, user: str) -> dict[str, Any] | None:
        payload = {
            "model": self.config.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.35},
        }
        req = urllib.request.Request(
            self.config.ollama_url.rstrip("/") + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.ai_timeout) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
            content = (((obj or {}).get("message") or {}).get("content") or "").strip()
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @staticmethod
    def _duration_profile(seconds: int) -> int:
        # Local I2V currently produces 2-6s clips. Keep planned shots at ~5s so
        # AUTO PRODUCE does not silently shorten long storyboard scenes.
        return max(2, min(24, int(math.ceil(max(5, seconds) / 5.0))))

    @staticmethod
    def _camera_for(i: int, total: int) -> dict[str, str]:
        recipes = [
            ("Wide establishing", "eye level", "slow dolly in"),
            ("Medium", "eye level", "slow tracking"),
            ("Close-up", "eye level", "subtle push in"),
            ("Low angle medium", "low angle", "tracking forward"),
            ("Over shoulder", "shoulder height", "gentle pan"),
            ("Hero wide", "slightly low", "slow orbit"),
        ]
        framing, angle, move = recipes[i % len(recipes)]
        if i == total - 1:
            framing, angle, move = recipes[-1]
        return {"framing": framing, "angle": angle, "movement": move}

    def _fallback_plan(self, req: dict[str, Any]) -> dict[str, Any]:
        idea = str(req.get("idea") or "Một video ngắn hấp dẫn").strip()
        duration = max(5, min(600, int(req.get("duration_seconds") or 30)))
        platform = str(req.get("platform") or "TikTok/Reels")
        ratio = str(req.get("aspect_ratio") or ("9:16" if platform.lower() in {"tiktok", "reels", "shorts", "tiktok/reels"} else "16:9"))
        style = str(req.get("style") or "cinematic, polished, modern")
        audience = str(req.get("audience") or "người xem phổ thông")
        goal = str(req.get("goal") or "thu hút người xem và truyền tải ý chính rõ ràng")
        character_lock = bool(req.get("character_lock", True))
        quality_priority = str(req.get("quality_priority") or "quality_first")
        count = self._duration_profile(duration)
        scene_len = duration / count
        hook = f"Mở đầu gây tò mò ngay về: {idea}"
        phases = ["HOOK", "SETUP", "DEVELOP", "DETAIL", "PAYOFF", "PROOF", "CTA"]
        scenes = []
        for i in range(count):
            phase = phases[min(i, len(phases)-1)]
            start = round(i * scene_len, 1)
            end = round(duration if i == count - 1 else (i + 1) * scene_len, 1)
            camera = self._camera_for(i, count)
            if i == 0:
                visual = f"Cảnh mở đầu mạnh, hình ảnh chủ thể rõ ràng liên quan đến {idea}"
                voice = f"Điều gì sẽ xảy ra khi {idea.lower()}?"
            elif i == count - 1:
                visual = f"Hero shot kết thúc, tổng hợp cảm xúc/chủ đề của {idea}"
                voice = "Đó là câu chuyện. Hãy biến ý tưởng của bạn thành video của riêng mình."
            else:
                visual = f"Phát triển ý tưởng {idea}, tập trung một hành động hoặc chi tiết duy nhất"
                voice = f"Từng bước, câu chuyện được mở ra rõ hơn cho {audience}."
            identity_rule = "same primary character identity across all scenes, preserve face, hair, body proportions and costume details, " if character_lock else ""
            img_prompt = (
                f"{visual}, {style}, {identity_rule}single clear subject, coherent composition, "
                f"clear detailed face, symmetric eyes, natural mouth, correct anatomy, cinematic lighting, "
                f"{camera['framing']}, {camera['angle']}, sharp high detail, {ratio} composition"
            )
            vid_prompt = (
                f"SUBJECT/STORY: {idea}. VISUAL: {visual}; {identity_rule}{style}. "
                f"CAMERA: {camera['framing']}, {camera['angle']}, {camera['movement']}. "
                f"STYLE: {style}. SHOT {i+1}: ACTION: {visual}. "
                "SOUND: precise ambience and scene-appropriate Foley/SFX; preserve dialogue clarity when present. "
                "Natural motion, stable identity, preserve face and costume, coherent anatomy, sharp subject, cinematic motion, no jitter, no morphing, no face drift. Cut."
            )
            scenes.append({
                "id": i + 1,
                "shot_label": f"Shot {i+1}",
                "phase": phase,
                "start": start,
                "end": end,
                "duration": round(end-start, 1),
                "visual": visual,
                "action": visual,
                "camera": camera,
                "voice": voice,
                "caption": voice,
                "image_prompt": img_prompt,
                "video_prompt": vid_prompt,
                "sound_design": "ambient atmosphere + precise scene Foley/SFX; keep dialogue/voice clear when present",
                "sfx": "ambient / scene-appropriate",
                "transition": "Cut",
            })
        return {
            "title": idea[:80],
            "concept": {
                "idea": idea,
                "goal": goal,
                "audience": audience,
                "platform": platform,
                "duration_seconds": duration,
                "aspect_ratio": ratio,
                "style": style,
                "hook": hook,
                "story_theme": idea,
                "story_emotion": str(req.get("story_emotion") or "cinematic, emotionally clear"),
                "visual_style": style,
                "character_lock": character_lock,
                "quality_priority": quality_priority,
            },
            "script": {
                "structure": "Hook → Setup → Develop → Payoff → CTA",
                "narration": " ".join(s["voice"] for s in scenes),
            },
            "scenes": scenes,
            "voice_plan": {
                "delivery": str(req.get("voice_style") or "tự nhiên, rõ, có nhịp"),
                "timing_rule": "voice drives shot duration; do not cut words; extend with B-roll when needed",
            },
            "caption_plan": {
                "enabled": bool(req.get("captions", True)),
                "rules": ["1-2 dòng", "safe-area", "không che mặt", "căn theo voice", "highlight từ khóa vừa phải"],
            },
            "music_plan": {
                "mood": str(req.get("music_mood") or "cinematic phù hợp nội dung"),
                "ducking": "-10 đến -16 dB dưới voice; tăng lại giữa các câu",
            },
            "quality_policy": {
                "priority": quality_priority,
                "character_lock": character_lock,
                "character_anchor": "generate one dedicated anchor for character-led stories; reuse it through img2img/edit when supported",
                "image_gate": ["resolution", "decode", "contrast", "sharpness"],
                "video_gate": ["playable stream", "resolution", "fps", "duration", "mostly-black detection"],
                "repair": "retry only failed scene; maximum depends on Draft/Balanced/High/Final",
                "final_master": "1080p target, high quality encoder, controlled sharpen, no fake detail claims",
            },
            "edit_plan": {
                "pace": "nhịp nhanh ở hook, ổn định ở nội dung, chậm hơn ở hero shot",
                "assembly": "voice-first → fit shots → transitions → music ducking → captions → final QC",
                "qc": ["không frame đen", "không cắt voice", "subtitle đúng timing", "audio không clipping", "aspect ratio đúng"],
            },
            "handoff": {
                "image_module": "tao_anh_ai",
                "video_module": "tao_video_ai",
                "caption_module": "phu_de",
                "music_module": "am_nhac",
                "edit_module": "chinh_sua_video",
                "cut_module": "cat_video",
            },
        }

    def build_plan(self, req: dict[str, Any]) -> dict[str, Any]:
        fallback = self._fallback_plan(req)
        system = """VAI TRÒ:
Bạn là một đạo diễn video A.I. chuyên nghiệp. Nhiệm vụ của bạn là biến bất kỳ ý tưởng/kịch bản nào người dùng đưa vào thành kế hoạch sản xuất và prompt video hoàn chỉnh, rõ ràng, không mơ hồ.

BẮT BUỘC MỖI KẾ HOẠCH PHẢI TUÂN THEO 5 PHẦN SAU:
1. CHỦ ĐỀ - CẢM XÚC CÂU CHUYỆN: 1-2 câu, nêu đúng chủ đề và cảm xúc chính; không tự đổi ý người dùng.
2. HÌNH ẢNH: mô tả chi tiết nhân vật, môi trường, màu sắc, ánh sáng. Nhân vật phải nhất quán xuyên mọi cảnh: cùng mặt, tóc, tỷ lệ cơ thể, trang phục, màu, phụ kiện và identity.
3. CAMERA: mỗi shot phải chỉ rõ cỡ cảnh, góc máy và chuyển động camera.
4. PHONG CÁCH: tông màu + ánh sáng trong một cụm ngắn, nhất quán toàn video.
5. SHOTS: tối đa 4-6 shot cho một video ngắn khi có thể. Mỗi shot phải có nhãn Shot 1, Shot 2...; viết hành động ở thì hiện tại; mô tả hành động chính xác, thiết kế âm thanh/không khí/SFX cụ thể; kết thúc shot bằng Cut.

CÁC QUY TẮC BẮT BUỘC:
- Nhân vật phải đồng nhất ở mọi cảnh.
- Viết mô tả hành động ở thì hiện tại.
- Không thêm nhân vật, đạo cụ, địa điểm hay hành động mà kịch bản không yêu cầu khi chế độ strict/script_lock bật.
- Nếu chi tiết chưa được người dùng chỉ định thì giữ UNSPECIFIED hoặc dùng lựa chọn trung tính; không bịa chi tiết quan trọng.
- Camera phải cụ thể, mang tính điện ảnh nhưng không được thay đổi nội dung kịch bản.
- Âm thanh phải cụ thể: ambience, Foley/SFX, voice/dialogue nếu có.
- Mỗi shot phải có action + sound_design + transition='Cut' (shot đầu có thể fade-in nhưng vẫn kết thúc bằng Cut).
- Prompt ảnh/video ưu tiên nhân vật rõ, giải phẫu đúng, mặt ổn định, hình nét, không jitter, không morphing, không face drift.
- Khi character_lock=true, giữ tuyệt đối identity nhân vật xuyên cảnh.
- Khi quality_priority=quality_first/final, ưu tiên chất lượng hình ảnh và consistency hơn tốc độ.
- Không bịa file, model, asset hoặc kết quả đã tạo.

ĐẦU RA:
Trả JSON duy nhất, không markdown. Giữ schema chính: title, concept, script, scenes, voice_plan, caption_plan, music_plan, quality_policy, edit_plan.
concept phải có thêm: story_theme, story_emotion, visual_style.
Mỗi scene phải có: id, shot_label, phase, start, end, duration, visual, action, camera{framing,angle,movement}, voice, caption, image_prompt, video_prompt, sound_design, sfx, transition.
video_prompt của từng scene phải được viết như một prompt đạo diễn hoàn chỉnh, theo đúng thứ tự: SUBJECT/STORY -> VISUAL -> CAMERA -> STYLE -> SHOT ACTION + SOUND.
"""
        project_id = str(req.get("project_id") or "").strip() or None
        if project_id:
            explicit_project_memory = {}
            for key in ("style", "aspect_ratio", "platform", "audience", "voice_style", "music_mood", "character_reference_id", "character_id", "location_id", "style_id"):
                value = req.get(key)
                if value not in (None, "", [], {}):
                    explicit_project_memory[key] = value
            if explicit_project_memory:
                self.memory.upsert_project(project_id, explicit_project_memory)
        memory_context = self.memory.resolve(project_id=project_id, user_command=req)
        memory_rules = """

MEMORY CONTRACT (BẮT BUỘC):
- Ưu tiên theo thứ tự: USER COMMAND > PROJECT MEMORY > VIDEO PLAYBOOK > FEEDBACK MEMORY > MODEL DEFAULTS.
- VIDEO PLAYBOOK là quy tắc sản xuất lâu dài, không được tự ý sửa.
- PROJECT MEMORY giữ character/location/style/voice/reference của dự án hiện tại.
- FEEDBACK MEMORY chỉ là kinh nghiệm đã lưu; nếu mâu thuẫn với lệnh hiện tại thì lệnh hiện tại thắng.
- Không được coi memory là bằng chứng rằng asset/video đã được tạo.
"""
        system = system + memory_rules
        user = json.dumps({"request": req, "memory_context": memory_context, "fallback_schema_example": fallback}, ensure_ascii=False)
        ai = self._ollama_json(system, user)
        plan = ai if self._valid_plan(ai) else fallback
        # Never let an LLM response silently drop the quality/identity contract.
        plan.setdefault("concept", {})
        plan["concept"].setdefault("character_lock", fallback["concept"]["character_lock"])
        plan["concept"].setdefault("quality_priority", fallback["concept"]["quality_priority"])
        plan.setdefault("quality_policy", fallback["quality_policy"])
        plan["concept"].setdefault("story_theme", fallback["concept"].get("story_theme"))
        plan["concept"].setdefault("story_emotion", fallback["concept"].get("story_emotion"))
        plan["concept"].setdefault("visual_style", fallback["concept"].get("visual_style"))
        # Enforce the director prompt contract even when Ollama returns a partial scene schema.
        for idx, scene in enumerate(plan.get("scenes") or [], 1):
            scene.setdefault("id", idx)
            scene.setdefault("shot_label", f"Shot {idx}")
            scene.setdefault("action", scene.get("visual") or "UNSPECIFIED")
            scene.setdefault("sound_design", scene.get("sfx") or "ambient / scene-appropriate")
            scene["transition"] = "Cut"
            cam = scene.get("camera") if isinstance(scene.get("camera"), dict) else {}
            cam.setdefault("framing", "UNSPECIFIED")
            cam.setdefault("angle", "UNSPECIFIED")
            cam.setdefault("movement", "UNSPECIFIED")
            scene["camera"] = cam
            if not str(scene.get("video_prompt") or "").strip():
                scene["video_prompt"] = (
                    f"SUBJECT/STORY: {plan['concept'].get('story_theme','UNSPECIFIED')}. "
                    f"VISUAL: {scene.get('visual','UNSPECIFIED')}. "
                    f"CAMERA: {cam['framing']}, {cam['angle']}, {cam['movement']}. "
                    f"STYLE: {plan['concept'].get('visual_style','UNSPECIFIED')}. "
                    f"{scene['shot_label']}: ACTION: {scene.get('action','UNSPECIFIED')}. "
                    f"SOUND: {scene.get('sound_design','ambient / scene-appropriate')}. Cut."
                )
        if plan["concept"].get("character_lock"):
            lock_img = " same primary character identity across all scenes, preserve face, hair, body proportions, costume and colors, clear detailed face, correct anatomy"
            lock_vid = " preserve the exact same character identity, face, hair, body proportions and costume; no face drift, no morphing, stable sharp subject"
            for scene in plan.get("scenes") or []:
                if lock_img.lower() not in str(scene.get("image_prompt") or "").lower():
                    scene["image_prompt"] = str(scene.get("image_prompt") or scene.get("visual") or "") + "." + lock_img
                if "no face drift" not in str(scene.get("video_prompt") or "").lower():
                    scene["video_prompt"] = str(scene.get("video_prompt") or scene.get("visual") or "") + "." + lock_vid
        plan["meta"] = {
            "planner": "ollama" if ai and self._valid_plan(ai) else "deterministic_fallback",
            "model": self.config.ollama_model if ai and self._valid_plan(ai) else None,
            "created_at": time.time(),
            "version": "7.0-director-memory",
            "memory": {
                "project_id": project_id,
                "playbook": memory_context.get("video_playbook", {}).get("name"),
                "project_memory_loaded": bool(memory_context.get("project_memory")),
                "feedback_loaded": len(memory_context.get("feedback_memory") or []),
                "priority": memory_context.get("priority"),
            },
        }
        return plan

    @staticmethod
    def _valid_plan(plan: Any) -> bool:
        if not isinstance(plan, dict):
            return False
        scenes = plan.get("scenes")
        return isinstance(scenes, list) and len(scenes) >= 2 and all(isinstance(x, dict) for x in scenes)

    def patch_scene(self, plan: dict[str, Any], scene_id: int, instruction: str) -> dict[str, Any]:
        scenes = plan.get("scenes") if isinstance(plan, dict) else None
        if not isinstance(scenes, list):
            raise ValueError("Plan không có scenes hợp lệ")
        target = next((s for s in scenes if int(s.get("id", -1)) == int(scene_id)), None)
        if target is None:
            raise ValueError("Không tìm thấy scene")
        instruction = str(instruction or "").strip()
        if not instruction:
            raise ValueError("Thiếu yêu cầu chỉnh scene")
        system = """Bạn sửa đúng MỘT shot trong kế hoạch video. Giữ nguyên mọi field không liên quan. Trả JSON của shot duy nhất, không markdown. Mọi sửa đổi phải giữ Prompt Contract: chủ đề/cảm xúc -> hình ảnh -> camera -> phong cách -> action+sound; giữ identity nhân vật; hành động ở thì hiện tại; không tự thêm nội dung ngoài instruction; kết thúc shot bằng Cut."""
        ai = self._ollama_json(system, json.dumps({"scene": target, "instruction": instruction}, ensure_ascii=False))
        if isinstance(ai, dict) and ai.get("id") == target.get("id"):
            new_scene = ai
        else:
            new_scene = dict(target)
            new_scene["visual"] = f"{target.get('visual','')} | Điều chỉnh: {instruction}"
            new_scene["image_prompt"] = f"{target.get('image_prompt','')}. Requested change: {instruction}. Preserve all unrelated attributes."
            new_scene["video_prompt"] = f"{target.get('video_prompt','')}. Requested change: {instruction}. Preserve identity and continuity."
        plan = json.loads(json.dumps(plan, ensure_ascii=False))
        for i, s in enumerate(plan["scenes"]):
            if int(s.get("id", -1)) == int(scene_id):
                plan["scenes"][i] = new_scene
                break
        plan.setdefault("meta", {})["updated_at"] = time.time()
        return plan

    def save_project(self, plan: dict[str, Any]) -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        title = str(plan.get("title") or "video")
        folder = self.root / f"{stamp}_{self._slug(title)}"
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "project.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        shots = [
            "# SHOT LIST\n",
            *[
                f"## Scene {s.get('id')} · {s.get('start')}–{s.get('end')}s\n"
                f"- Visual: {s.get('visual','')}\n"
                f"- Camera: {json.dumps(s.get('camera',{}), ensure_ascii=False)}\n"
                f"- Voice: {s.get('voice','')}\n"
                f"- Image prompt: {s.get('image_prompt','')}\n"
                f"- Video prompt: {s.get('video_prompt','')}\n"
                for s in plan.get("scenes", [])
            ],
        ]
        (folder / "shot_list.md").write_text("\n".join(shots), encoding="utf-8")
        return folder

    def route_module_task(self, text: str, requested_output: str | None = None, explicit_module: str | None = None) -> dict[str, Any]:
        route = route_task(text, requested_output=requested_output, explicit_module=explicit_module)
        data = route.as_dict()
        data["contract"] = MODULE_CONTRACTS[route.module]
        return data

    def memory_context(self, project_id: str | None = None, user_command: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.memory.resolve(project_id=project_id, user_command=user_command)

    def update_project_memory(self, project_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        return self.memory.upsert_project(project_id, memory)

    def remember_feedback(self, text: str, project_id: str | None = None, scope: str = "video", kind: str = "preference") -> dict[str, Any]:
        return self.memory.add_feedback(text=text, project_id=project_id, scope=scope, kind=kind)

    def status(self) -> dict[str, Any]:
        return {
            "ready": True,
            "phase": "preproduction+auto_produce",
            "build": "v7-director-memory",
            "features": ["idea", "script", "storyboard", "shot_list", "prompts", "camera", "voice_plan", "caption_plan", "music_plan", "edit_plan", "scene_patch", "auto_produce", "character_lock", "character_anchor", "image_qa", "video_qa", "repair_loop", "final_1080p_master", "strict_module_router", "module_isolation", "video_playbook_memory", "project_memory", "feedback_memory", "memory_priority"],
            "planner": "ollama-if-available + deterministic fallback",
            "ollama_url": self.config.ollama_url,
            "ollama_model": self.config.ollama_model,
            "module_contracts": MODULE_CONTRACTS,
            "memory": self.memory.status(),
        }
