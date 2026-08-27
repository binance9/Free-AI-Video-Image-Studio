"""ASCII staging for Windows-native 3D libraries.

Some native exporters used by the local 3D stack do not reliably open absolute
Windows paths containing non-ASCII characters.  This helper creates a short
ASCII-only working directory outside OneDrive, while final assets are copied
back to the normal project workspace afterwards.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def has_non_ascii(path: str | Path) -> bool:
    return any(ord(ch) > 127 for ch in str(path))


def create_ascii_staging_dir() -> Path:
    candidates: list[Path] = []
    for key in ("LOCALAPPDATA", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value) / "AIVF3D_TMP")
    system_drive = os.environ.get("SystemDrive")
    if system_drive:
        candidates.append(Path(system_drive + "\\") / "AIVF3D_TMP")
    candidates.append(Path(tempfile.gettempdir()) / "AIVF3D_TMP")

    errors: list[str] = []
    for base in candidates:
        if has_non_ascii(base):
            continue
        try:
            base.mkdir(parents=True, exist_ok=True)
            return Path(tempfile.mkdtemp(prefix="job_", dir=str(base))).resolve()
        except OSError as exc:
            errors.append(f"{base}: {exc}")

    raise RuntimeError(
        "Không tạo được thư mục tạm ASCII cho xatlas trên Windows. "
        + " | ".join(errors[-3:])
    )
