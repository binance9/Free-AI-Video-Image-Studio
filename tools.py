from __future__ import annotations
from typing import Any, Dict
from maintenance import SystemMaintenance


class ToolError(Exception):
    pass


class ComputerTools:
    """Deliberately narrow tool surface: health checks + safe cleanup only."""
    def __init__(self, config, confirm_callback=None):
        self.config = config
        self.confirm_callback = confirm_callback or (lambda title, msg: False)
        self.maint = SystemMaintenance(config)

    def maintenance_report(self):
        return self.maint.health_report()

    def scan_junk(self):
        return self.maint.scan_report()

    def check_gpu_cuda(self):
        return self.maint.check_cuda()

    def clean_safe_junk(self):
        preview = self.maint.scan_report()
        if not self.confirm_callback(
            "XÁC NHẬN DỌN RÁC AN TOÀN",
            preview + "\n\nChỉ các mục đánh dấu SAFE sẽ bị xóa. Tiếp tục?",
        ):
            raise ToolError("Chủ nhân đã hủy dọn rác.")
        return self.maint.clean_safe()

    def execute(self, tool: str, args: Dict[str, Any] | None = None):
        local = {
            "maintenance_report": self.maintenance_report,
            "scan_junk": self.scan_junk,
            "check_gpu_cuda": self.check_gpu_cuda,
            "clean_safe_junk": self.clean_safe_junk,
        }
        if tool not in local:
            raise ToolError(
                "GÀ MAINTENANCE chỉ được phép kiểm tra máy và dọn rác an toàn. "
                f"Không có công cụ: {tool}"
            )
        return local[tool]()
