"""Public interface for free local 3D generation backends."""
from .service import Local3DService
from .workspace import Model3DWorkspace

__all__ = ["Local3DService", "Model3DWorkspace"]

from .job_manager import Model3DJobManager

from .texture_cuda_patch import apply_texture_cuda_patch

from .windows_path_staging import create_ascii_staging_dir, has_non_ascii
