from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path


class OllamaClient:
    def __init__(
        self,
        url="http://127.0.0.1:11434",
        main_model="qwen3:30b",
        fast_model="qwen3:8b",
        chat_keep_alive="90s",
        deep_keep_alive=0,
    ):
        self.url = str(url).rstrip("/")
        self.main_model = str(main_model)
        self.fast_model = str(fast_model)
        self.chat_keep_alive = chat_keep_alive
        self.deep_keep_alive = deep_keep_alive

    @property
    def model(self):
        # compatibility with old status UI
        return self.main_model

    def installed_models(self):
        try:
            with urllib.request.urlopen(self.url + "/api/tags", timeout=3) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
            return [str(x.get("name") or x.get("model") or "") for x in obj.get("models", [])]
        except Exception:
            return []

    def _choose_model(self, fast=False):
        installed = self.installed_models()
        wanted = self.fast_model if fast else self.main_model
        if wanted in installed:
            return wanted
        # Main brain may still be downloading. Use 8B only as a temporary availability fallback.
        if self.fast_model in installed:
            return self.fast_model
        return wanted

    def resolve_model(self, fast=False):
        """Public wrapper over _choose_model, used by ModelRouter (V12) to
        know/log which real model name a routed call will actually hit,
        without duplicating the installed-models fallback logic."""
        return self._choose_model(fast=fast)

    def _request(self, payload, timeout=120):
        req = urllib.request.Request(
            self.url + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def chat(self, messages, *, fast=False, deep=False, json_mode=False, num_predict_override=None):
        model = self._choose_model(fast=fast)
        num_predict = num_predict_override or ((2400 if deep else 700) if json_mode else (1800 if deep else 500))
        payload = {
            "model": model,
            "stream": False,
            "messages": messages,
            "keep_alive": self.deep_keep_alive if deep else self.chat_keep_alive,
            "options": {
                "temperature": 0.03 if json_mode else (0.10 if not deep else 0.12),
                # deep=True enables thinking (below), and the reasoning trace itself
                # consumes num_predict before the model ever gets to the answer -
                # a deep call budgeted like a fast one comes back with empty content
                # once thinking alone eats the budget. Give deep calls real headroom.
                "num_predict": num_predict,
                "num_ctx": 8192,
            },
        }
        if json_mode:
            payload["format"] = "json"
        payload["think"] = bool(deep)
        # A caller-supplied budget (e.g. self-heal asking for a whole-file rewrite)
        # can dwarf the normal 210s deep timeout - scale it with the token budget
        # instead of hardcoding, so large overrides don't get cut off mid-generation.
        timeout = max(210 if deep else 120, num_predict // 8) if num_predict_override else (210 if deep else 120)
        try:
            data = self._request(payload, timeout)
        except Exception:
            payload.pop("think", None)
            data = self._request(payload, timeout)
        return str(data.get("message", {}).get("content") or "").strip()

    def json(self, messages, *, fast=False, deep=False, num_predict_override=None):
        raw = self.chat(messages, fast=fast, deep=deep, json_mode=True, num_predict_override=num_predict_override)
        try:
            return json.loads(raw)
        except Exception:
            a, b = raw.find("{"), raw.rfind("}")
            if a >= 0 and b > a:
                return json.loads(raw[a:b + 1])
            raise ValueError("AI không trả JSON hợp lệ")

    def translate_to_english(self, text: str) -> str:
        # Real bug found 2026-08-31: the local Stable Diffusion checkpoint's
        # CLIP text encoder is trained mostly on English captions - a Vietnamese
        # image-generation prompt gets largely ignored, producing an unrelated
        # generic image (confirmed by direct A/B testing: same prompt in
        # Vietnamese vs English gave a random unrelated scene vs the correctly
        # requested character). Translating to English first fixes the root
        # cause rather than patching prompt wording. Fast+non-thinking is
        # enough for a literal translation task - no reasoning needed.
        clean = str(text or "").strip()
        if not clean:
            return clean
        try:
            out = self.chat(
                [
                    {"role": "system", "content": (
                        "Dịch câu sau sang tiếng Anh, giữ nguyên nghĩa, dùng để làm prompt vẽ ảnh AI. "
                        "Chỉ trả về đúng câu tiếng Anh đã dịch, không giải thích, không thêm dấu ngoặc kép."
                    )},
                    {"role": "user", "content": clean},
                ],
                fast=True,
            )
        except Exception:
            return clean
        out = out.strip().strip('"').strip()
        return out or clean

    def status(self):
        names = self.installed_models()
        return {
            "ok": bool(names),
            "model": self._choose_model(False),
            "main_model": self.main_model,
            "fast_model": self.fast_model,
            "main_installed": self.main_model in names,
            "fast_installed": self.fast_model in names,
            "models": names,
        }

    def vision_model(self):
        names = self.installed_models()
        preferred = ("qwen3-vl:8b", "qwen3-vl", "qwen2.5-vl:7b", "qwen2.5vl:7b", "gemma3:12b", "gemma3:4b", "llava:7b", "llava")
        low = {n.lower(): n for n in names}
        for p in preferred:
            if p.lower() in low:
                return low[p.lower()]
        for n in names:
            s = n.lower()
            if "vision" in s or "qwen3-vl" in s or "qwen2.5-vl" in s or "llava" in s or s.startswith("gemma3:"):
                return n
        return None

    def vision_status(self):
        m = self.vision_model()
        return {"available": bool(m), "model": m, "note": "Vision local thật" if m else "Chưa có vision model; không giả vờ nhìn ảnh."}

    def analyze_image(self, image_path, request_text=""):
        model = self.vision_model()
        if not model:
            return {"available": False, "model": None, "summary": None, "note": "Chưa có vision model."}
        raw = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        payload = {
            "model": model,
            "stream": False,
            "keep_alive": "45s",
            # qwen3-vl is a thinking model: with a small budget the thinking phase alone
            # consumes it all and content comes back empty (done_reason=length, confirmed
            # by direct testing - 500 tokens => content=""; needed ~3200-4500 to reach
            # done_reason=stop with a real answer, and thinking length scales with how
            # complex/long request_text is). "think": False does not suppress thinking for
            # this model (tested, still emits a <think> block), so the fix is budget.
            "options": {"temperature": 0.02, "num_predict": 4500, "num_ctx": 8192},
            "messages": [{
                "role": "user",
                "content": "Mô tả trung thực ảnh này phục vụ đúng yêu cầu sau. Không đoán phần không nhìn thấy. Yêu cầu: " + str(request_text),
                "images": [raw],
            }],
        }
        try:
            data = self._request(payload, 260)
        except Exception as exc:
            return {"available": False, "model": model, "summary": None, "note": f"Vision call lỗi: {exc}"}
        return {"available": True, "model": model, "summary": str(data.get("message", {}).get("content") or "").strip()}

    def describe_character_image(self, image_path):
        # Deliberately NOT request-text-aware: embedding the owner's full instruction
        # (e.g. "tạo nhân vật cầm đao") into the description prompt was confirmed by
        # direct testing to make qwen3-vl hallucinate the image already matches the
        # request (e.g. describing a bow as a sword) instead of reporting ground truth -
        # a worse failure than empty content, since it silently defeats weapon-conflict
        # detection. A neutral, closed-ended prompt describes only what's really there.
        model = self.vision_model()
        if not model:
            return {"available": False, "model": None, "summary": None, "note": "Chưa có vision model."}
        raw = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        payload = {
            "model": model,
            "stream": False,
            "keep_alive": "45s",
            "options": {"temperature": 0.02, "num_predict": 4500, "num_ctx": 8192},
            "messages": [{
                "role": "user",
                "content": "Mô tả ngắn gọn nhân vật trong ảnh này bằng 2-3 câu tiếng Việt: giới tính, trang phục, màu sắc chính, và VŨ KHÍ đang cầm (nếu có). Chỉ mô tả những gì thấy được, không suy luận thêm.",
                "images": [raw],
            }],
        }
        try:
            data = self._request(payload, 260)
        except Exception as exc:
            return {"available": False, "model": model, "summary": None, "note": f"Vision call lỗi: {exc}"}
        return {"available": True, "model": model, "summary": str(data.get("message", {}).get("content") or "").strip()}
