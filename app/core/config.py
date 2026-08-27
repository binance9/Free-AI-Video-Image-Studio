from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Video Factory"
    base_dir: Path = BASE_DIR
    version: str = "0.8.9.3.3"
    db_path: Path = BASE_DIR / "data" / "factory.db"
    web_dir: Path = BASE_DIR / "web"
    editor_dir: Path = BASE_DIR / "data" / "editor_sessions"
    ai_image_dir: Path = BASE_DIR / "data" / "ai_images"
    model_3d_dir: Path = BASE_DIR / "data" / "3d_assets"
    do_vat_3d_dir: Path = BASE_DIR / "data" / "do_vat_3d"
    triposr_dir: Path = BASE_DIR / "tools" / "external" / "TripoSR"
    music_library_dir: Path = BASE_DIR / "data" / "music_library"
    facebook_download_dir: Path = BASE_DIR / "data" / "facebook_downloads"
    video_cleanup_runtime_dir: Path = BASE_DIR / "data" / "runtime_video_cleanup"
    video_cleanup_jobs_dir: Path = BASE_DIR / "data" / "video_cleanup_jobs"
    model_dir: Path = BASE_DIR / "data" / "models"
    whisper_model: str = "small"
    image_model: str = "stable-diffusion-v1-5/stable-diffusion-v1-5"


settings = Settings()
