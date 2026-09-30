from __future__ import annotations
import json, re, unicodedata
import requests

SYSTEM_PROMPT = r"""
Bạn là GÀ MAINTENANCE, AI chuyên trách bảo trì máy Windows.

PHẠM VI DUY NHẤT:
1) Kiểm tra tình trạng máy: ổ đĩa, CPU, RAM, NVIDIA GPU, VRAM, Torch/CUDA.
2) Quét rác và dọn rác an toàn.

KHÔNG ĐƯỢC:
- sửa code, ghi/xóa file tùy ý, điều khiển chuột/bàn phím, mở web, tải file, tắt process;
- xóa model Hugging Face đã hoàn chỉnh;
- xóa Python/Torch package đang active;
- tự dùng shell/CMD/PowerShell;
- nhận việc ngoài bảo trì máy. Nếu người dùng hỏi ngoài phạm vi, nói ngắn gọn rằng GÀ MAINTENANCE chỉ dọn rác và kiểm tra máy.

QUY TẮC DỌN:
- Luôn scan_junk trước clean_safe_junk.
- clean_safe_junk có lớp xác nhận ở công cụ; không được tìm cách bỏ qua.
- Mục REVIEW chỉ báo cáo, không được xóa.
- File Hugging Face .incomplete chỉ SAFE khi đủ cũ và không có tiến trình tải HF/Xet.
- Cache pip được phép purge.
- ~orch/~‑rch chỉ SAFE khi Torch active được xác minh đang import từ thư mục torch chuẩn.
- TEMP chỉ dọn mục đủ cũ; mục đang khóa phải bỏ qua.

Mỗi lần trả đúng MỘT JSON object:
{"type":"tool","tool":"maintenance_report","args":{},"message":"đang kiểm tra máy"}
{"type":"tool","tool":"scan_junk","args":{},"message":"đang quét rác"}
{"type":"tool","tool":"check_gpu_cuda","args":{},"message":"đang kiểm tra GPU/CUDA"}
{"type":"tool","tool":"clean_safe_junk","args":{},"message":"đang dọn các mục SAFE"}
{"type":"final","message":"kết quả ngắn gọn bằng tiếng Việt"}
"""


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


class GaAgent:
    def __init__(self, config, tools):
        self.config = config
        self.tools = tools
        self.history = []

    @property
    def ollama_url(self):
        return self.config.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")

    def ollama_available(self):
        try:
            return requests.get(self.ollama_url + "/api/tags", timeout=1.0).ok
        except Exception:
            return False

    def _chat(self, messages):
        r = requests.post(
            self.ollama_url + "/api/chat",
            json={"model": self.config.get("ollama_model", "qwen3:8b"), "stream": False,
                  "messages": messages, "options": {"temperature": 0.0}},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    @staticmethod
    def _parse_json(text):
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                raise ValueError("Model không trả JSON.")
            return json.loads(m.group(0))

    def run(self, user_text):
        # Deterministic routing for the common maintenance commands: no LLM needed.
        fallback = self._fallback(user_text)
        if fallback is not None:
            return fallback
        if not self.ollama_available():
            return ("Con này chỉ chuyên dọn rác và kiểm tra tình trạng máy. Nói 'quét rác', 'dọn rác', 'kiểm tra máy' hoặc 'kiểm tra GPU'.", [])
        try:
            return self._smart(user_text)
        except Exception as e:
            return (f"AI local đang lỗi ({type(e).__name__}). Các nút Quét máy / Quét rác / Dọn an toàn vẫn dùng được.", [])

    def _smart(self, user_text):
        conv = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history[-6:], {"role": "user", "content": user_text}]
        logs = []
        final = ""
        for _ in range(int(self.config.get("max_agent_steps", 6))):
            obj = self._parse_json(self._chat(conv))
            if obj.get("type") == "final":
                final = str(obj.get("message", "Xong.")); break
            if obj.get("type") != "tool":
                final = "Con này chỉ chuyên dọn rác và kiểm tra máy."; break
            tool = str(obj.get("tool", ""))
            logs.append(f"→ {tool}")
            try:
                obs = self.tools.execute(tool, obj.get("args") or {})
            except Exception as e:
                obs = f"TOOL_ERROR: {type(e).__name__}: {e}"
            logs.append(obs)
            conv += [{"role":"assistant","content":json.dumps(obj, ensure_ascii=False)},
                     {"role":"user","content":"KẾT QUẢ CÔNG CỤ:\n"+obs+"\nHoàn tất hoặc dùng đúng công cụ bảo trì tiếp theo."}]
        if not final:
            final = "Đã xong bước bảo trì."
        self.history += [{"role":"user","content":user_text},{"role":"assistant","content":final}]
        return final, logs

    def _fallback(self, raw):
        s = strip_accents(raw.lower().strip())
        if any(k in s for k in ("don rac", "xoa rac", "clean rac", "don cache")):
            logs=[]
            scan=self.tools.execute("scan_junk",{}); logs.append(scan)
            out=self.tools.execute("clean_safe_junk",{}); logs.append(out)
            return "Dọn an toàn đã chạy xong.", logs
        if any(k in s for k in ("quet rac", "kiem tra rac", "rac may")):
            out=self.tools.execute("scan_junk",{})
            return "Đã quét rác.", [out]
        if any(k in s for k in ("kiem tra gpu", "kiem tra cuda", "torch cuda", "gpu cuda")):
            out=self.tools.execute("check_gpu_cuda",{})
            return "Đã kiểm tra GPU/CUDA.", [out]
        if any(k in s for k in ("kiem tra may", "tinh trang may", "suc khoe may", "kiem tra he thong", "cau hinh may")):
            out=self.tools.execute("maintenance_report",{})
            return "Đã kiểm tra tình trạng máy.", [out]
        maintenance_words=("o c", "o dia", "cpu", "ram", "vram", "nhiet do", "dung luong", "cache", "torch", "python", "hugging face", "huggingface")
        if any(k in s for k in maintenance_words):
            return None
        return ("Con này chỉ chuyên DỌN RÁC và KIỂM TRA TÌNH TRẠNG MÁY. Tao không nhận việc khác.", [])
