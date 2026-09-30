from __future__ import annotations

import os
import zipfile
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
OUT = BASE / "AI_VIDEO_FACTORY_SOURCE_NHE_GUI_GA.zip"
TREE = BASE / "_GA_SOURCE_TREE.txt"

# Chỉ lấy source/config text; không lấy model, video, ảnh, env nặng.
ALLOW_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".md", ".txt", ".bat", ".cmd", ".ps1",
    ".sql", ".xml", ".vue", ".svelte",
}

ALLOW_NAMES = {
    "requirements.txt", "pyproject.toml", "poetry.lock",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "vite.config.js", "vite.config.ts",
    "webpack.config.js", "webpack.config.ts",
    "next.config.js", "next.config.mjs", "next.config.ts",
    "tsconfig.json", "jsconfig.json",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitignore", ".env.example", ".env.sample",
}

# Tuyệt đối không gom các thư mục nặng / riêng tư / sinh ra tự động.
SKIP_DIR_NAMES = {
    ".git", ".svn", ".hg",
    ".venv", "venv", "env", "__pycache__",
    "node_modules",
    ".next", ".nuxt", ".svelte-kit",
    "dist", "build", "coverage",
    "models", "model", "checkpoints", "weights",
    "loras", "lora", "embeddings",
    "cache", ".cache", "tmp", "temp",
    "outputs", "output", "renders", "render",
    "uploads", "downloads",
    "videos", "video", "images", "image",
    "assets_generated", "generated",
    "logs", "log",
}

# Những tên file có khả năng chứa secret thật thì không gửi.
SKIP_FILE_NAMES = {
    ".env", "credentials.json", "secrets.json",
    "token.json", "tokens.json",
}

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB / file source

def should_skip_dir(path: Path) -> bool:
    name = path.name.lower()
    if name in SKIP_DIR_NAMES:
        return True
    # Ollama / HuggingFace / model cache hay nằm trong tên thư mục dài.
    bad_parts = ("checkpoint", "model_cache", "huggingface", "ollama", "torch_cache")
    return any(x in name for x in bad_parts)

def allowed_file(path: Path) -> bool:
    name_lower = path.name.lower()

    if name_lower in SKIP_FILE_NAMES:
        return False

    if name_lower in ALLOW_NAMES:
        return True

    if path.suffix.lower() not in ALLOW_EXT:
        return False

    # Không gửi source map/minified bundles lớn.
    if name_lower.endswith(".min.js") or name_lower.endswith(".map"):
        return False

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False

    return True

def main():
    files = []
    skipped_dirs = []

    for dirpath, dirnames, filenames in os.walk(BASE):
        current = Path(dirpath)

        # Không tự gom ZIP collector / output của chính nó.
        if current == BASE:
            pass

        keep_dirs = []
        for d in dirnames:
            p = current / d
            if should_skip_dir(p):
                skipped_dirs.append(str(p.relative_to(BASE)))
            else:
                keep_dirs.append(d)
        dirnames[:] = keep_dirs

        for filename in filenames:
            p = current / filename

            if p.name in {
                "TAO_ZIP_NHE_GUI_GA.bat",
                "collector_source_ga.py",
                "DOC_TRUOC_KHI_GUI.txt",
                "AI_VIDEO_FACTORY_SOURCE_NHE_GUI_GA.zip",
                "_GA_SOURCE_TREE.txt",
            }:
                continue

            if allowed_file(p):
                files.append(p)

    # File tree rất hữu ích để tao biết app bố trí thế nào.
    tree_lines = [
        "AI VIDEO FACTORY - SOURCE TREE FOR GÀ INTEGRATION",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "=== FILES INCLUDED ===",
    ]
    for p in sorted(files):
        try:
            rel = p.relative_to(BASE)
            size = p.stat().st_size
            tree_lines.append(f"{rel} | {size} bytes")
        except Exception:
            pass

    tree_lines += ["", "=== HEAVY DIRS SKIPPED ==="]
    tree_lines += sorted(set(skipped_dirs))
    TREE.write_text("\n".join(tree_lines), encoding="utf-8")

    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(TREE, TREE.name)
        for p in files:
            try:
                z.write(p, p.relative_to(BASE))
            except Exception as e:
                print("Bỏ qua:", p, e)

    try:
        TREE.unlink()
    except Exception:
        pass

    mb = OUT.stat().st_size / (1024 * 1024)
    print()
    print("==============================================")
    print("ĐÃ TẠO ZIP SOURCE NHẸ")
    print("==============================================")
    print("File:", OUT.name)
    print(f"Dung lượng: {mb:.2f} MB")
    print(f"Số file source/config: {len(files)}")
    print()
    print("GỬI FILE ZIP NÀY CHO GÀ:")
    print(OUT)
    print()
    print("Nếu ZIP vẫn quá lớn, báo dung lượng cho tao để tao làm bộ lọc nhỏ hơn.")

if __name__ == "__main__":
    main()
