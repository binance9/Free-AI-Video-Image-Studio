"""Vision-backed QA for deterministic renders of generated character GLBs."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

from app.modules.ga_brain.model_client import OllamaClient

VIEW_ORDER = ("front_full", "front_face", "left_three_quarter", "right_three_quarter", "side")


class CharacterVisualQA:
    def __init__(self, client=None):
        self.client = client or OllamaClient()

    @staticmethod
    def montage(render_paths: dict[str, str], output_path: str | Path) -> Path:
        missing = [view for view in VIEW_ORDER if not Path(render_paths.get(view, "")).is_file()]
        if missing:
            raise ValueError("Missing QA render views: " + ", ".join(missing))
        tile = 512
        canvas = Image.new("RGB", (tile * 3, tile * 2), (18, 21, 27))
        draw = ImageDraw.Draw(canvas)
        for index, view in enumerate(VIEW_ORDER):
            image = Image.open(render_paths[view]).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
            x, y = (index % 3) * tile, (index // 3) * tile
            canvas.paste(image, (x, y))
            draw.rectangle((x, y, x + 230, y + 26), fill=(0, 0, 0))
            draw.text((x + 7, y + 6), view.upper(), fill=(255, 255, 255))
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, "JPEG", quality=92)
        return output

    @staticmethod
    def _json_object(text: str) -> dict | None:
        text = str(text or "").strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except Exception:
                return None

    def evaluate(self, render_paths: dict[str, str], output_dir: str | Path) -> dict:
        output_dir = Path(output_dir).resolve()
        montage = self.montage(render_paths, output_dir / "qa_montage.jpg")
        status = self.client.vision_status()
        if not status.get("available"):
            return {
                "status": "UNSUPPORTED", "pass": False, "score": None, "model": None,
                "note": "No vision-capable evaluator is installed; renders are saved for manual review.",
                "montage": str(montage),
            }
        request = (
            "Đánh giá CHỈ những gì nhìn thấy trong montage 5 góc của cùng một nhân vật 3D. "
            "FRONT_FACE phải thấy được toàn bộ mặt. Trả về DUY NHẤT JSON hợp lệ, không markdown, schema: "
            '{"face_pass":true,"eyes_pass":true,"mouth_pass":true,"body_pass":true,'
            '"score":0,"face_evidence":"...","eyes_evidence":"...","mouth_evidence":"...",'
            '"body_evidence":"...","texture_evidence":"..."}. '
            "face_pass chỉ true khi mặt đọc rõ, đầu không dị dạng, texture mặt không vỡ và tóc không che/méo toàn bộ mặt. "
            "eyes_pass chỉ true khi thấy hai mắt tương đối cân, không mất/nhòe rõ, không cross-eye/lác rõ. "
            "mouth_pass chỉ true khi miệng nằm đúng vùng mặt, không méo, không há bất thường. "
            "body_pass chỉ true khi tỷ lệ thân hợp lý, không đầu quá to hoặc chân quá ngắn ngoài chủ đích style. "
            "Nếu view không đủ rõ để xác nhận tiêu chí nào thì tiêu chí đó phải false. score là chất lượng tổng 0..100."
        )
        response = self.client.analyze_image(montage, request)
        if not response.get("available") or not response.get("summary"):
            return {
                "status": "UNSUPPORTED", "pass": False, "score": None, "model": status.get("model"),
                "note": response.get("note") or "Vision evaluator returned no result.", "montage": str(montage),
            }
        parsed = self._json_object(response["summary"])
        required = ("face_pass", "eyes_pass", "mouth_pass", "body_pass")
        if not isinstance(parsed, dict) or any(type(parsed.get(key)) is not bool for key in required):
            return {
                "status": "UNSUPPORTED", "pass": False, "score": None, "model": status.get("model"),
                "note": "Vision evaluator did not return the required boolean JSON; no score was fabricated.",
                "raw": response["summary"], "montage": str(montage),
            }
        try:
            score = max(0.0, min(100.0, float(parsed.get("score", 0))))
        except (TypeError, ValueError):
            score = 0.0
        overall = all(parsed[key] for key in required)
        return {
            "status": "PASS" if overall else "FAIL", "pass": overall, "score": score,
            "model": status.get("model"), "face_pass": parsed["face_pass"],
            "eyes_pass": parsed["eyes_pass"], "mouth_pass": parsed["mouth_pass"],
            "body_pass": parsed["body_pass"],
            "evidence": {key: str(parsed.get(key, "")) for key in (
                "face_evidence", "eyes_evidence", "mouth_evidence", "body_evidence", "texture_evidence"
            )},
            "montage": str(montage), "raw": response["summary"],
        }
