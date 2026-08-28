from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.api_core import router as core_router
from app.modules.chinh_sua_video.api_chinh_sua_video import router as video_editor_router
from app.core.api_settings import router as settings_router
from app.modules.cong_cu_van_ban.api_cong_cu_van_ban import router as text_router
from app.modules.tao_anh_ai.api_tao_anh_ai import router as ai_image_router
from app.modules.am_nhac.api_am_nhac import router as music_router
from app.modules.phu_de.api_phu_de import router as caption_router
from app.modules.nhan_vat_3d.api_nhan_vat_3d import router as model_3d_router
from app.modules.tai_video.api_tai_video import router as facebook_video_router
from app.modules.tai_video_web.api_tai_video_web import router as tai_video_web_router
from app.modules.lam_sach_video.api_lam_sach_video import router as video_cleanup_router
from app.core.api_job_control import router as job_control_router
from app.core.api_system import router as system_router
from app.modules.nhan_vat_2d.api_nhan_vat_2d import router as character_2d_router
from app.modules.nhan_vat_game_ready.api_nhan_vat_game_ready import router as game_ready_3d_router
from app.modules.do_vat_3d.api_do_vat_3d import router as do_vat_3d_router
from app.api.model_3d_library_routes import router as model_3d_library_router
from app.core.config import settings
from app.core.module_registry import DirectorAI
from app.modules.chinh_sua_video import VideoEditor
from app.modules.chinh_sua_video.workspace import VideoWorkspace
from app.modules.tao_anh_ai import AiImageWorkspace, LocalImageService, AiImageJobManager
from app.modules.am_nhac import LocalMusicLibrary
from app.modules.phu_de import LocalCaptionService, LocalTranslationService
from app.modules.nhan_vat_3d import Local3DService, Model3DWorkspace, Model3DJobManager
from app.modules.nhan_vat_3d.turntable_video import TurntableVideoExporter
from app.modules.tai_video import FacebookVideoDownloader, FacebookVideoJobManager
from app.modules.tai_video_web import WebVideoDownloader, WebVideoJobManager
from app.modules.lam_sach_video import VideoCleanupRuntime, VideoCleanupJobManager
from app.modules.nhan_vat_2d import Character2DService
from app.modules.nhan_vat_game_ready import GameReady3DService, GameReadyJobManager
from app.modules.do_vat_3d import DoVat3DService, DoVat3DJobManager
from app.modules.model_3d_library import Model3DLibrary
from app.storage.database import Database
from app.storage.project_memory import ProjectMemory


from app.modules.ban_do_3d.api_ban_do_3d import router as ban_do_3d_router

def create_app(db_path=None, editor_dir=None) -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version)
    db = Database(db_path or settings.db_path)
    memory = ProjectMemory(db)

    settings.model_dir.mkdir(parents=True, exist_ok=True)
    settings.music_library_dir.mkdir(parents=True, exist_ok=True)
    settings.ai_image_dir.mkdir(parents=True, exist_ok=True)
    settings.model_3d_dir.mkdir(parents=True, exist_ok=True)
    settings.facebook_download_dir.mkdir(parents=True, exist_ok=True)
    settings.tai_video_web_dir.mkdir(parents=True, exist_ok=True)
    settings.video_cleanup_jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.do_vat_3d_dir.mkdir(parents=True, exist_ok=True)

    app.state.memory = memory
    app.state.director = DirectorAI(memory)
    app.state.video_editor = VideoEditor()
    app.state.video_workspace = VideoWorkspace(editor_dir or settings.editor_dir, settings.web_dir / "stickers")
    app.state.model_dir = settings.model_dir
    app.state.ai_image_workspace = AiImageWorkspace(settings.ai_image_dir)
    app.state.ai_image_service = LocalImageService(settings.image_model, settings.model_dir / "image")
    app.state.ai_image_jobs = AiImageJobManager(app.state.ai_image_service, app.state.ai_image_workspace)
    app.state.character_2d_service = Character2DService(root=settings.base_dir / "data" / "character_2d_addon")
    app.state.model_3d_workspace = Model3DWorkspace(settings.model_3d_dir)
    app.state.model_3d_service = Local3DService(settings.triposr_dir, settings.model_dir / "3d", app.state.ai_image_service, settings.base_dir)
    app.state.model_3d_jobs = Model3DJobManager(app.state.model_3d_service, app.state.model_3d_workspace, settings.model_3d_dir / "_jobs")
    app.state.model_3d_turntable = TurntableVideoExporter(settings.model_3d_dir)
    app.state.game_ready_3d_service = GameReady3DService(settings.model_3d_dir / "_game_ready")
    app.state.game_ready_3d_jobs = GameReadyJobManager(app.state.game_ready_3d_service, app.state.model_3d_workspace)
    app.state.model_3d_library = Model3DLibrary(settings.base_dir / "data" / "3d_library", app.state.model_3d_workspace)
    app.state.do_vat_3d_workspace = Model3DWorkspace(settings.do_vat_3d_dir / "assets")
    app.state.do_vat_3d_service = DoVat3DService(
        settings.triposr_dir, settings.model_dir / "3d", app.state.ai_image_service, settings.base_dir
    )
    app.state.do_vat_3d_jobs = DoVat3DJobManager(
        app.state.do_vat_3d_service, app.state.do_vat_3d_workspace, settings.do_vat_3d_dir / "_jobs"
    )
    app.state.music_library = LocalMusicLibrary(settings.music_library_dir)
    app.state.caption_service = LocalCaptionService(settings.whisper_model, settings.model_dir / "whisper")
    app.state.translation_service = LocalTranslationService()
    app.state.facebook_video_downloader = FacebookVideoDownloader(settings.facebook_download_dir)
    app.state.facebook_video_jobs = FacebookVideoJobManager(
        app.state.facebook_video_downloader, app.state.video_workspace, settings.facebook_download_dir / "_jobs"
    )
    app.state.tai_video_web_downloader = WebVideoDownloader(settings.tai_video_web_dir / "output")
    app.state.tai_video_web_jobs = WebVideoJobManager(
        app.state.tai_video_web_downloader, app.state.video_workspace, settings.tai_video_web_dir / "_jobs"
    )
    app.state.video_cleanup_runtime = VideoCleanupRuntime(
        settings.base_dir, settings.video_cleanup_runtime_dir, settings.model_dir / "video_cleanup"
    )
    app.state.video_cleanup_jobs = VideoCleanupJobManager(
        app.state.video_cleanup_runtime, app.state.video_workspace, settings.video_cleanup_jobs_dir
    )

    for router in (core_router, video_editor_router, settings_router, text_router, ai_image_router, character_2d_router, music_router, caption_router, model_3d_router, game_ready_3d_router, do_vat_3d_router, facebook_video_router, tai_video_web_router, video_cleanup_router, job_control_router, system_router):
        app.include_router(router)

    app.include_router(ban_do_3d_router)
    app.include_router(model_3d_library_router)
    app.mount("/static", StaticFiles(directory=settings.web_dir), name="static")

    @app.get("/")
    def home():
        return FileResponse(settings.web_dir / "index.html", headers={"Cache-Control": "no-store, max-age=0"})

    return app


app = create_app()
