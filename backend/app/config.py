"""平台全局配置。

所有路径均以项目根目录为基准推导，避免在代码中出现相对路径漂移。
可执行文件、监听地址与端口统一由项目根目录的 ``.env`` 提供（见 ``.env.example``），
真实环境变量优先级更高，便于在 CI 或多机部署时覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

from .env import ROOT

DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
MODULES_DIR = DATA_DIR / "modules"
STYLES_DIR = DATA_DIR / "styles"
TEXTURES_DIR = DATA_DIR / "texturesets"

GENERATOR_DIR = ROOT / "generator"
GENERATOR_ENTRY = GENERATOR_DIR / "entry.py"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Blender 默认安装路径，可用 .env / 环境变量覆盖
DEFAULT_BLENDER_EXE = r"D:\blender\blender.exe"
BLENDER_EXE = Path(os.environ.get("FB_BLENDER_EXE", DEFAULT_BLENDER_EXE))

# 后端监听地址与端口
HOST = os.environ.get("FB_HOST", "127.0.0.1")
PORT = int(os.environ.get("FB_PORT", "8756"))

# 前端 dev server（CORS 白名单用）
FRONTEND_HOST = os.environ.get("FB_FRONTEND_HOST", "127.0.0.1")
FRONTEND_PORT = int(os.environ.get("FB_FRONTEND_PORT", "5120"))
CORS_ORIGINS = [
    f"http://{FRONTEND_HOST}:{FRONTEND_PORT}",
    f"http://localhost:{FRONTEND_PORT}",
]

# 后台构建任务的相关限制
JOB_TIMEOUT_SECONDS = int(os.environ.get("FB_JOB_TIMEOUT", "180"))
MAX_CONCURRENT_JOBS = 1  # MVP 阶段串行执行，避免多个 Blender 实例争抢内存/显卡

# 贴图规格限制
MAX_TEXTURE_SIZE = 2048
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
