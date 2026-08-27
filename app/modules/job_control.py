from __future__ import annotations

import os
import subprocess
from typing import Any


class JobCancelled(RuntimeError):
    """Raised when a user explicitly cancels a long-running local job."""


def terminate_process(proc: Any) -> None:
    """Terminate only the process tree spawned for one AI Video Factory job."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
