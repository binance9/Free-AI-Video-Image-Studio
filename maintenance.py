from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import psutil
except Exception:
    psutil = None

GB = 1024 ** 3
MB = 1024 ** 2


def _size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    for root, _, files in os.walk(path, onerror=lambda _e: None):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _fmt(n: int) -> str:
    if n >= GB:
        return f"{n / GB:.2f} GB"
    if n >= MB:
        return f"{n / MB:.0f} MB"
    return f"{n / 1024:.0f} KB"


def _run(args, timeout=20):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, (cp.stdout or "").strip(), (cp.stderr or "").strip()
    except Exception as e:
        return 999, "", f"{type(e).__name__}: {e}"


@dataclass
class JunkItem:
    category: str
    path: str
    bytes: int
    safe: bool
    reason: str

    def as_dict(self):
        return {
            "category": self.category,
            "path": self.path,
            "bytes": self.bytes,
            "size": _fmt(self.bytes),
            "safe": self.safe,
            "reason": self.reason,
        }


class SystemMaintenance:
    """Windows health + conservative junk cleaner.

    SAFE means this class is willing to remove it automatically. Anything
    ambiguous is report-only. It never removes completed HF models or the
    active Python/Torch package tree.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.home = Path.home()
        self.appdata = Path(os.environ.get("APPDATA", self.home / "AppData/Roaming"))
        self.local = Path(os.environ.get("LOCALAPPDATA", self.home / "AppData/Local"))
        self.temp = Path(os.environ.get("TEMP", self.local / "Temp"))
        self.hf = self.home / ".cache" / "huggingface"
        self.site = self.appdata / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages"

    def _disk(self):
        root = Path(os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else Path("/")
        u = shutil.disk_usage(root)
        return {"drive": str(root), "total": u.total, "used": u.used, "free": u.free}

    def _gpu(self):
        rc, out, err = _run([
            "nvidia-smi",
            "--query-gpu=name,temperature.gpu,utilization.gpu,memory.total,memory.used,driver_version",
            "--format=csv,noheader,nounits",
        ])
        if rc != 0 or not out:
            return {"available": False, "error": err or "nvidia-smi không khả dụng"}
        first = out.splitlines()[0]
        parts = [x.strip() for x in first.split(",")]
        if len(parts) < 6:
            return {"available": True, "raw": first}
        return {
            "available": True,
            "name": parts[0], "temp_c": parts[1], "util_pct": parts[2],
            "vram_total_mb": parts[3], "vram_used_mb": parts[4], "driver": parts[5],
        }

    def _torch(self):
        code = (
            "import json,torch; print(json.dumps({"
            "'version':torch.__version__,'cuda_available':torch.cuda.is_available(),"
            "'cuda':torch.version.cuda,'path':torch.__file__,"
            "'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
        )
        rc, out, err = _run([sys.executable, "-c", code], timeout=30)
        if rc != 0:
            return {"available": False, "error": err[-500:]}
        try:
            return {"available": True, **json.loads(out.splitlines()[-1])}
        except Exception:
            return {"available": False, "error": out[-500:]}

    def _relevant_download_active(self) -> bool:
        if psutil is None:
            return False
        needles = ("hf_xet", "huggingface", "hf.exe")
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                s = ((p.info.get("name") or "") + " " + " ".join(p.info.get("cmdline") or [])).lower()
                if any(n in s for n in needles):
                    return True
            except Exception:
                pass
        return False

    def health_data(self):
        disk = self._disk()
        data = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "python_exe": sys.executable,
            "disk": disk,
            "gpu": self._gpu(),
            "torch": self._torch(),
        }
        if psutil:
            vm = psutil.virtual_memory()
            data["cpu"] = {"logical": psutil.cpu_count(True), "usage_pct": psutil.cpu_percent(interval=.3)}
            data["ram"] = {"total": vm.total, "available": vm.available, "usage_pct": vm.percent}
        return data

    def health_report(self):
        d = self.health_data()
        disk = d["disk"]
        threshold = float(self.config.get("low_disk_threshold_gb", 25))
        lines = [
            "=== TÌNH TRẠNG MÁY ===",
            f"Ổ C: trống {_fmt(disk['free'])} / {_fmt(disk['total'])}"
            + ("  ⚠ THẤP" if disk["free"] / GB < threshold else "  ✓"),
        ]
        if "cpu" in d:
            lines.append(f"CPU: {d['cpu']['usage_pct']:.0f}% | {d['cpu']['logical']} luồng")
        if "ram" in d:
            lines.append(f"RAM: {d['ram']['usage_pct']:.0f}% | trống {_fmt(d['ram']['available'])}")
        g = d["gpu"]
        if g.get("available"):
            lines.append(f"GPU: {g.get('name','NVIDIA')} | {g.get('temp_c','?')}°C | tải {g.get('util_pct','?')}% | VRAM {g.get('vram_used_mb','?')}/{g.get('vram_total_mb','?')} MB")
        else:
            lines.append("GPU: không đọc được nvidia-smi")
        t = d["torch"]
        if t.get("available"):
            lines.append(f"Torch: {t.get('version')} | CUDA {t.get('cuda')} | CUDA available={t.get('cuda_available')}")
            lines.append(f"Torch path: {t.get('path')}")
        else:
            lines.append("Torch: không import được trong runtime của app")
        return "\n".join(lines)

    def scan_junk(self):
        items: list[JunkItem] = []

        pip_cache = self.local / "pip" / "Cache"
        if pip_cache.exists():
            n = _size(pip_cache)
            if n:
                items.append(JunkItem("pip_cache", str(pip_cache), n, True,
                                      "Cache gói cài pip; xóa không gỡ package đã cài."))

        # Stale pip rename directories caused by interrupted upgrades, e.g. ~orch/~‑rch.
        if self.site.exists():
            active_torch = self._torch()
            active_path = str(active_torch.get("path", "")).lower()
            for name in ("~orch", "~-rch"):
                p = self.site / name
                if p.exists():
                    safe = bool(active_path and name.lower() not in active_path and "site-packages\\torch\\" in active_path.replace("/", "\\"))
                    items.append(JunkItem("stale_torch_backup", str(p), _size(p), safe,
                                          "Thư mục đổi tên tạm của pip; chỉ SAFE khi Torch active trỏ vào thư mục torch chuẩn."))

        # Old Hugging Face partials only. Never completed blobs/snapshots.
        active_dl = self._relevant_download_active()
        min_age = float(self.config.get("hf_incomplete_min_age_hours", 24)) * 3600
        now = time.time()
        if self.hf.exists():
            for p in self.hf.rglob("*"):
                if not p.is_file() or not (p.name.endswith(".incomplete") or p.name.endswith(".partial")):
                    continue
                try:
                    age = now - p.stat().st_mtime
                    n = p.stat().st_size
                except OSError:
                    continue
                safe = (age >= min_age) and not active_dl
                items.append(JunkItem("hf_incomplete", str(p), n, safe,
                                      "Chỉ xóa file tải dở đủ cũ và khi không có tiến trình Hugging Face/Xet đang tải."))

        # User TEMP: old entries only; current/in-use entries will fail closed.
        days = float(self.config.get("temp_max_age_days", 7))
        cutoff = now - days * 86400
        temp_bytes = 0
        temp_candidates = []
        if self.temp.exists():
            try:
                children = list(self.temp.iterdir())
            except OSError:
                children = []
            for p in children:
                try:
                    if p.stat().st_mtime < cutoff:
                        n = _size(p)
                        temp_bytes += n
                        temp_candidates.append(str(p))
                except OSError:
                    pass
        if temp_bytes:
            items.append(JunkItem("old_temp", str(self.temp), temp_bytes, True,
                                  f"Chỉ mục TEMP cũ hơn {days:g} ngày; file đang khóa sẽ tự bỏ qua."))

        return items

    def scan_report(self):
        items = self.scan_junk()
        if not items:
            return "=== QUÉT RÁC ===\nKhông thấy rác thuộc nhóm SAFE/được nhận diện."
        safe = sum(x.bytes for x in items if x.safe)
        review = sum(x.bytes for x in items if not x.safe)
        lines = ["=== QUÉT RÁC ===", f"Có thể dọn an toàn: {_fmt(safe)} | Cần xem lại: {_fmt(review)}"]
        for x in sorted(items, key=lambda i: i.bytes, reverse=True):
            lines.append(f"[{'SAFE' if x.safe else 'REVIEW'}] {x.category}: {_fmt(x.bytes)}\n  {x.path}\n  {x.reason}")
        return "\n".join(lines)

    def _clean_old_temp(self):
        days = float(self.config.get("temp_max_age_days", 7))
        cutoff = time.time() - days * 86400
        freed = 0
        failed = 0
        if not self.temp.exists():
            return freed, failed
        try:
            children = list(self.temp.iterdir())
        except OSError:
            return 0, 1
        for p in children:
            try:
                if p.stat().st_mtime >= cutoff:
                    continue
                n = _size(p)
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                freed += n
            except Exception:
                failed += 1
        return freed, failed

    def clean_safe(self):
        before = self._disk()["free"]
        items = self.scan_junk()
        logs = []
        failed = 0

        # purge pip via pip itself, not blind deletion
        pip = next((x for x in items if x.category == "pip_cache" and x.safe), None)
        if pip:
            rc, out, err = _run([sys.executable, "-m", "pip", "cache", "purge"], timeout=180)
            logs.append(f"pip cache purge: {'PASS' if rc == 0 else 'FAIL'}" + (f" | {out[-300:]}" if out else ""))
            failed += int(rc != 0)

        for x in items:
            if not x.safe or x.category in ("pip_cache", "old_temp"):
                continue
            p = Path(x.path)
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
                logs.append(f"Đã dọn {x.category}: {_fmt(x.bytes)} | {p}")
            except Exception as e:
                failed += 1
                logs.append(f"Bỏ qua {p}: {type(e).__name__}")

        if any(x.category == "old_temp" and x.safe for x in items):
            freed_temp, temp_failed = self._clean_old_temp()
            failed += temp_failed
            logs.append(f"TEMP cũ: đã dọn khoảng {_fmt(freed_temp)}, bỏ qua {temp_failed} mục đang khóa/lỗi")

        after = self._disk()["free"]
        freed = max(0, after - before)
        logs.insert(0, f"=== DỌN AN TOÀN ===\nGiải phóng thực tế: {_fmt(freed)} | Còn trống ổ C: {_fmt(after)}")
        if failed:
            logs.append(f"Có {failed} thao tác không dọn được; không ép xóa.")
        logs.append("Không xóa model Hugging Face hoàn chỉnh và không xóa package Torch/Python active.")
        return "\n".join(logs)

    def check_cuda(self):
        t = self._torch()
        g = self._gpu()
        if not t.get("available"):
            return "Torch runtime: FAIL\n" + str(t.get("error", ""))
        lines = [
            "=== GPU / CUDA ===",
            f"Torch: {t.get('version')}",
            f"CUDA build: {t.get('cuda')}",
            f"CUDA available: {t.get('cuda_available')}",
            f"GPU Torch: {t.get('gpu')}",
        ]
        if g.get("available"):
            lines.append(f"nvidia-smi: {g.get('name')} | {g.get('temp_c')}°C | VRAM {g.get('vram_used_mb')}/{g.get('vram_total_mb')} MB")
        return "\n".join(lines)
