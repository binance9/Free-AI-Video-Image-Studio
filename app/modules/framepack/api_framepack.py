"""FramePack backend — engine tao video AI dai chay local (khong hien UI rieng).

Chiро wired vao khung AI Video Director cu:
  POST /api/framepack/script             -> kich ban tieng Viet => anh (SDXL) + video (FramePack)
  GET  /api/framepack/script-status/{id} -> tien do job; done => video_url
  GET  /api/framepack/video/{name}       -> serve file mp4
  GET  /api/framepack/status             -> server song chet
  POST /api/framepack/start | /stop      -> quan ly server engine (an)
"""
from __future__ import annotations

import json as _json
import os as _os
import random as _random
import shutil as _shutil
import socket
import subprocess
import time as _time
import urllib.error as _urlerr
import urllib.request as _urlreq
import uuid as _uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "data" / "runtime_framepack"
VENV_PY = RUNTIME / "venv" / "Scripts" / "python.exe"
SRC = ROOT / "tools" / "external" / "FramePack"
LOG = RUNTIME / "framepack_server.log"
READY = RUNTIME / "READY.txt"
PORT = 7890
FP_URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = ROOT / "data" / "ai_videos"

router = APIRouter(prefix="/api/framepack", tags=["framepack"])

_JOBS: dict[str, dict] = {}


def _port_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


class _State:
    proc: subprocess.Popen | None = None


api_framepack_state = _State()


def _http_json(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = _json.dumps(payload).encode("utf-8") if payload is not None else None
    req = _urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
    with _urlreq.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read().decode("utf-8"))


def _upload_file(path: Path) -> str:
    """Upload anh vao Gradio (multipart tay), tra ve path phia server."""
    boundary = "----framepack" + _uuid.uuid4().hex
    body = b""
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
             f"filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n").encode("utf-8")
    body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    req = _urlreq.Request(f"{FP_URL}/gradio_api/upload", data=body,
                          headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with _urlreq.urlopen(req, timeout=60) as r:
        arr = _json.loads(r.read().decode("utf-8"))
    return arr[0]


def _ollama_translate(request, kichban: str) -> dict:
    """Dich kich ban tieng Viet thanh 2 prompt tieng Anh qua ollama local."""
    cfg_path = ROOT / "config.json"
    base, model = "http://127.0.0.1:11434", "qwen3:8b"
    try:
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        base = cfg.get("ollama_url", base).rstrip("/")
        model = cfg.get("ollama_model", model)
    except Exception:
        pass
    sys_prompt = (
        "Ban bien kich ban video tieng Viet thanh 2 prompt TIENG ANH cho AI tao video. "
        'Chi tra JSON: {"image_prompt": "...", "video_prompt": "..."}. '
        "image_prompt: mo ta khung hinh DAU tien (ngoai hinh nhan vat, canh, anh sang, phong cach cinematic) de AI ve anh. "
        "video_prompt: mo ta HANH DONG se xay ra trong video (chuyen dong tu tu, camera). "
        "Khong dang dan, khong giai thi dap them."
    )
    try:
        out = _http_json(f"{base}/api/chat", {
            "model": model, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0.4},
            "messages": [{"role": "system", "content": sys_prompt},
                         {"role": "user", "content": kichban[:1500]}],
        }, timeout=120)
        raw = (out.get("message") or {}).get("content") or "{}"
        j = _json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        if j.get("image_prompt") and j.get("video_prompt"):
            return j
    except Exception:
        pass
    # fallback: dung thang kich ban
    return {"image_prompt": "cinematic photo, " + kichban[:300],
            "video_prompt": kichban[:300]}


@router.get("/status")
def status():
    installed = READY.exists() and VENV_PY.exists() and (SRC / "demo_gradio.py").exists()
    return {"installed": installed, "running": _port_open(), "url": FP_URL,
            "note": "Engine FramePack chay an; dieu khien qua khung AI Video Director."}


@router.post("/start")
def start():
    if _port_open():
        return {"ok": True, "already_running": True, "url": FP_URL}
    if not READY.exists():
        return {"ok": False, "error": "Chua cai — chay INSTALL_FRAMEPACK.bat truoc."}
    with open(LOG, "ab") as lf:
        api_framepack_state.proc = subprocess.Popen(
            [str(VENV_PY), "demo_gradio.py", "--port", str(PORT)],
            cwd=str(SRC), stdout=lf, stderr=lf,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    return {"ok": True, "already_running": False, "url": FP_URL}


@router.post("/stop")
def stop():
    p = api_framepack_state.proc
    if p is not None and p.poll() is None:
        p.terminate()
        return {"ok": True, "stopped": True}
    return {"ok": True, "stopped": False}


@router.post("/script")
def script_to_video(payload: dict, request):
    """Kich ban tieng Viet (+ ANH TUY CHON) -> video.
    Co anh: dung anh do, kich ban chi lam prompt chuyen dong.
    Khong anh: ollama dich -> SDXL ve anh dau -> FramePack sinh video."""
    kichban = str(payload.get("kichban", "")).strip()
    if len(kichban) < 5:
        return {"ok": False, "error": "Kich ban qua ngan — viet ro hon."}
    try:
        so_giay = min(max(int(payload.get("so_giay", 5)), 1), 60)
    except Exception:
        so_giay = 5
    if not READY.exists():
        return {"ok": False, "error": "Chua cai FramePack — chay INSTALL_FRAMEPACK.bat."}
    if not _port_open():
        start()
        for _ in range(90):
            if _port_open():
                break
            _time.sleep(1.0)
        if not _port_open():
            return {"ok": False, "error": "Engine FramePack khong mo duoc — bam lai sau it giay."}

    # 1) anh nguon: upload tu may (base64) hoac AI tu ve
    import base64 as _b64
    img_url = None
    anh_b64 = str(payload.get("anh_base64", "") or "")
    if anh_b64.startswith("data:image"):
        try:
            raw = _b64.b64decode(anh_b64.split(",", 1)[1])
            RUNTIME.mkdir(parents=True, exist_ok=True)
            p_in = RUNTIME / f"in_{_uuid.uuid4().hex[:8]}.png"
            p_in.write_bytes(raw)
            img_path, img_url = p_in, None  # anh cua chu, khong can preview URL
            prompts = None
        except Exception as e:
            return {"ok": False, "error": f"Doc anh loi: {e}"}
    else:
        prompts = _ollama_translate(request, kichban)
        try:
            svc = request.app.state.ai_image_service
            ws = request.app.state.ai_image_workspace
            img = svc.generate(prompts["image_prompt"], "cinematic", "1536x1024", "medium")
            saved = ws.save(img)
            img_path, img_url = ws.path(saved["image_id"]), saved["url"]
        except Exception as e:
            return {"ok": False, "error": f"Loi tao anh: {e}"}

    # 2) xep job FramePack (prompt chuyen dong = kich ban da dich; co anh thi dich rieng 1 prompt)
    if prompts is None:
        prompts = _ollama_translate(request, "(chi tao prompt video_prompt) " + kichban)
        prompts["image_prompt"] = "(dung anh cua chu)"
    try:
        srv_path = _upload_file(img_path)
        body = {"data": [
            {"path": srv_path, "meta": {"_type": "gradio.FileData"}},
            prompts["video_prompt"], "", _random.randint(1, 10**9),
            so_giay, 9, 25, 1.0, 10.0, 0.0, 6, True, 16,
        ]}
        ev = _http_json(f"{FP_URL}/gradio_api/call/process", body)
        event_id = ev.get("event_id")
        if not event_id:
            return {"ok": False, "error": "FramePack khong nhan job."}
    except Exception as e:
        return {"ok": False, "error": f"Loi xep job FramePack: {e}"}

    job_id = _uuid.uuid4().hex[:12]
    _JOBS[job_id] = {"event_id": event_id, "kichban": kichban[:200], "at": _time.time(),
                     "so_giay": so_giay, "image_url": img_url, "prompts": prompts}
    return {"ok": True, "job": job_id, "image_url": img_url,
            "image_prompt": prompts["image_prompt"], "video_prompt": prompts["video_prompt"],
            "note": f"Dang sinh video {so_giay} giay — mat vai phut/giay tren card 16GB."}


@router.get("/script-status/{job}")
def script_status(job: str):
    info = _JOBS.get(job)
    if not info:
        return {"ok": False, "error": "Khong thay job."}
    url = f"{FP_URL}/gradio_api/call/process/{info['event_id']}"
    last_event, last_data = "generating", None
    try:
        req = _urlreq.Request(url)
        with _urlreq.urlopen(req, timeout=10) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if line.startswith("event:"):
                    last_event = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and last_event != "heartbeat":
                    last_data = line.split(":", 1)[1].strip()
    except _urlerr.URLError:
        return {"ok": True, "done": False, "stage": "dang chay"}
    except Exception:
        pass
    if last_event == "complete" and last_data:
        try:
            arr = _json.loads(last_data)
            vfile = (arr[0] or {}).get("path") if arr and isinstance(arr[0], dict) else None
            if vfile and Path(vfile).is_file():
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                name = f"framepack_{job}.mp4"
                _shutil.copy(vfile, OUT_DIR / name)
                info["done"] = True
                return {"ok": True, "done": True, "video_url": f"/api/framepack/video/{name}",
                        "image_url": info.get("image_url")}
            return {"ok": False, "done": True, "error": "Job ket thuc nhung khong thay video."}
        except Exception as e:
            return {"ok": False, "done": True, "error": f"Doc ket qua loi: {e}"}
    if last_event == "error":
        return {"ok": False, "done": True, "error": "FramePack bao loi job."}
    return {"ok": True, "done": False, "stage": "dang render..."}


@router.get("/video/{name}")
def video_file(name: str):
    safe = Path(name).name
    p = OUT_DIR / safe
    if safe.startswith("framepack_") and p.is_file():
        return FileResponse(p, media_type="video/mp4", filename=safe)
    return {"ok": False, "error": "Khong thay video."}
