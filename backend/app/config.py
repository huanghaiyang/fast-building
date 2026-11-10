"""平台全局配置。

所有路径均以项目根目录为基准推导，避免在代码中出现相对路径漂移。
Blender 可执行文件支持通过环境变量 ``FB_BLENDER_EXE`` 覆盖，便于在多台机器上部署。
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/app/config.py -> 项目根目录
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
MODULES_DIR = DATA_DIR / "modules"
STYLES_DIR = DATA_DIR / "styles"
TEXTURES_DIR = DATA_DIR / "texturesets"

GENERATOR_DIR = ROOT / "generator"
GENERATOR_ENTRY = GENERATOR_DIR / "entry.py"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Blender 默认安装路径，可用环境变量覆盖
DEFAULT_BLENDER_EXE = r"D:\blender\blender.exe"
BLENDER_EXE = Path(os.environ.get("FB_BLENDER_EXE", DEFAULT_BLENDER_EXE))

# 后台构建任务的相关限制
JOB_TIMEOUT_SECONDS = int(os.environ.get("FB_JOB_TIMEOUT", "180"))
MAX_CONCURRENT_JOBS = 1  # MVP 阶段串行执行，避免多个 Blender 实例争抢内存/显卡

# 贴图规格限制
MAX_TEXTURE_SIZE = 2048
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
