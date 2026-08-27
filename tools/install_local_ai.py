"""Install free local AI Python dependencies. Model weights download on first use."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements_local_ai.txt"


def main() -> int:
    print("=" * 68)
    print(" AI VIDEO FACTORY 0.8 - SETUP FREE LOCAL AI")
    print(" Khong can OpenAI API key. Khong co phi theo luot.")
    print("=" * 68)
    print("Dang cai cac thu vien local. PyTorch co the tai kha lon...")
    code = subprocess.call([sys.executable, "-m", "pip", "install", "-r", str(REQ)], cwd=str(ROOT))
    if code:
        print("\n[LOI] Cai thu vien that bai. Xem dong loi o tren.")
        return code
    print("\n[OK] Da cai xong thu vien AI local.")
    print("Lan dau dung Phu de/AI Anh/Dich, model se duoc tai mien phi ve may.")
    print("Sau khi model da co tren may, cac lan sau khong tinh phi theo luot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
