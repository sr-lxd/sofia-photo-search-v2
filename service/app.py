from pathlib import Path
import os
import logging
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from service.api.v1.router import api_router
from service.core.auth import get_request_policy, is_authenticated_request
from service.core.config import settings
from service.db import mysql
from service.core.logging import setup_logging
from service.core.runtime_warm import finish_startup_warm, mark_startup_warm_started, set_startup_component
from service.face.engine import get_face_engine
from service.index.manager import get_index_manager, get_vision_index_manager
from service.vision.engine import get_vision_engine

BASE_DIR = Path(__file__).resolve().parents[1]
UI_DIR = BASE_DIR / "ui"
PUBLIC_PATHS = {"/login", "/favicon.ico"}
PUBLIC_PREFIXES = ("/api/v1/auth",)


log = logging.getLogger(__name__)
_STARTUP_WARMED = False


def _path_is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _path_requires_auth(path: str) -> bool:
    return path == "/" or path.startswith("/ui/") or path.startswith("/api/")


def _warm_search_runtime_assets() -> None:
    global _STARTUP_WARMED
    if _STARTUP_WARMED:
        return
    _STARTUP_WARMED = True
    mark_startup_warm_started()
    try:
        get_index_manager().load()
        set_startup_component("face_index", True, "人脸索引已加载")
    except Exception:
        set_startup_component("face_index", False, "人脸索引加载失败")
        log.exception("startup face index warm failed")
    try:
        get_vision_index_manager().load()
        set_startup_component("vision_index", True, "视觉索引已加载")
    except Exception:
        set_startup_component("vision_index", False, "视觉索引加载失败")
        log.exception("startup vision index warm failed")
    try:
        get_face_engine()
        set_startup_component("face_engine", True, "人脸模型已加载")
    except Exception:
        set_startup_component("face_engine", False, "人脸模型加载失败")
        log.exception("startup face engine warm failed")
    try:
        get_vision_engine()
        set_startup_component("vision_engine", True, "视觉模型已加载")
    except Exception:
        set_startup_component("vision_engine", False, "视觉模型加载失败")
        log.exception("startup vision engine warm failed")
    startup = get_index_manager()
    vision = get_vision_index_manager()
    ok = bool(startup.exists() and vision.exists())
    finish_startup_warm(ok=ok, message="系统搜索已就绪" if ok else "系统预热部分未完成")


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Local Photo Face Search")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        path = request.url.path
        if _path_is_public(path) or not _path_requires_auth(path):
            return await call_next(request)
        policy = get_request_policy(request)
        if policy:
            request.state.policy = policy
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "未登录，请先输入密码"})
        return RedirectResponse(url="/login")

    app.include_router(api_router, prefix="/api/v1")
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    @app.on_event("startup")
    def _reconcile_scan_progress_on_startup():
        try:
            repaired_rows = mysql.stop_active_scan_progress_rows()
            if repaired_rows:
                log.warning("startup reconciled %s stale scan progress rows to stopped", repaired_rows)
        except Exception:
            log.exception("startup scan progress reconcile failed")
        if os.getenv("PHOTO_SEARCH_LAZY_MODELS") != "1":
            threading.Thread(target=_warm_search_runtime_assets, daemon=True).start()

    @app.get("/login")
    def login_page(request: Request):
        if is_authenticated_request(request):
            return RedirectResponse(url="/")
        login_path = UI_DIR / "login.html"
        if login_path.exists():
            return FileResponse(login_path)
        return {"status": "error", "message": "Login page not found", "ui_path": str(UI_DIR)}

    @app.get("/")
    def root():
        index_path = UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"status": "ok", "message": "UI not found", "ui_path": str(UI_DIR)}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service.app:app", host="0.0.0.0", port=settings.server.port, reload=False)
