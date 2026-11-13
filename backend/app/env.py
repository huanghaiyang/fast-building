"""极简 ``.env`` 读取（不引入 python-dotenv 依赖）。

约定：
- 只读取项目根目录的 ``.env``（模板见 ``.env.example``）；
- 真实环境变量优先于 ``.env``（``os.environ.setdefault``）；
- 支持 ``KEY=VALUE``、``#`` 注释、值两侧的引号。
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/app/env.py -> 项目根目录
ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """把 ``path`` 中的配置写入 os.environ（不覆盖已有变量）。"""
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv(ROOT / ".env")
