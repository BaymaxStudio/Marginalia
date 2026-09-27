"""FastAPI 入口"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.database import init_db
from app.logger import setup_logging, get_logger
from app.services.ai_adapter import NoAPIKeyError
from app.services.settings_service import get_all_safe
from app.routers import (
    documents,
    lookup,
    commentary,
    vocabulary,
    progress,
    settings,
)

app = FastAPI(title="AI Academic Reader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由（必须在 SPA fallback 之前注册）
app.include_router(documents.router, prefix="/api")
app.include_router(lookup.router, prefix="/api")
app.include_router(commentary.router, prefix="/api")
app.include_router(vocabulary.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

_app_logger = get_logger("main")


@app.exception_handler(NoAPIKeyError)
async def no_api_key_handler(request: Request, exc: NoAPIKeyError) -> JSONResponse:
    # 未配置 Key 是用户可处理的状态，把原因带给前端，而不是笼统的 500
    return JSONResponse(status_code=400, content={"detail": str(exc)})

# 前端静态文件路径
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
_FRONTEND_DIST = os.path.abspath(_FRONTEND_DIST)

@app.get("/api/health")
def health():
    return {"status": "ok"}


if os.path.exists(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(
        directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        root = Path(_FRONTEND_DIST).resolve()
        file_path = (root / path).resolve()
        if not file_path.is_relative_to(root):
            raise HTTPException(404, "文件不存在")
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))


@app.on_event("startup")
def on_startup():
    init_db()
    try:
        log_level = get_all_safe().get("log_level", "INFO")
    except Exception:
        log_level = "INFO"
    setup_logging(log_level)
    _app_logger.info("Marginalia backend started (log level: %s)", log_level)
