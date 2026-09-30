from __future__ import annotations

from fastapi import FastAPI, Request


def install_local_freshness(app: FastAPI) -> None:
    """Prevent stale localhost UI files after the owner edits the bot."""

    @app.middleware("http")
    async def _aivf_local_no_cache(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["X-AIVF-Local-Fresh"] = "1"
        return response
