"""FastAPI 应用入口。

包含：
- REST API（模块库 / 风格 / 贴图集 / 生成任务）；
- 产物静态服务：``/out`` 指向 data/jobs，``/tex`` 指向 data/texturesets；
- 若前端已构建（frontend/dist 存在），一并托管，实现单端口访问。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import jobs_api, resources
from .config import FRONTEND_DIST, JOBS_DIR, TEXTURES_DIR
from .services import previews


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动时后台预热模块预览资源，退出时停止预热线程。"""
    previews.start_prewarm()
    yield
    previews.stop_prewarm()


app = FastAPI(title="Fast Building Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5120", "http://127.0.0.1:5120"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resources.router)
app.include_router(jobs_api.router)

JOBS_DIR.mkdir(parents=True, exist_ok=True)
TEXTURES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/out", StaticFiles(directory=JOBS_DIR), name="out")
app.mount("/tex", StaticFiles(directory=TEXTURES_DIR), name="tex")

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


@app.get("/api")
def api_root() -> dict:
    return {"name": "Fast Building Platform", "docs": "/docs"}
