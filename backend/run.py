"""开发环境启动脚本：``python backend/run.py``。"""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

# 允许以脚本方式直接运行（backend 目录加入模块搜索路径）
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8756, reload=False)
