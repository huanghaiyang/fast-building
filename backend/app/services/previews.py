"""模块三维预览的生成与缓存。

预览与正式建筑共用 generator 中的几何函数：首次请求时调用一次 Blender
生成单模块 GLB，之后直接读取缓存。缓存失效条件为 generator 源码、
模块描述符或贴图集发生变化。
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path

from ..config import (
    BLENDER_EXE,
    DATA_DIR,
    GENERATOR_DIR,
    GENERATOR_ENTRY,
    MODULES_DIR,
    ROOT,
)

PREVIEWS_DIR = DATA_DIR / "previews"
PREVIEW_TIMEOUT_SECONDS = 120
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_MODULE_ID = re.compile(r"^[A-Za-z0-9_]+$")
_lock = threading.Lock()


def is_valid_module(module_id: str) -> bool:
    if not _MODULE_ID.match(module_id):
        return False
    return (MODULES_DIR / f"{module_id}.json").exists()


def _source_stamp() -> float:
    """取所有会影响预览结果的文件的最后修改时间。"""
    stamps: list[float] = []
    for pattern, directory in (
        ("**/*.py", GENERATOR_DIR),
        ("*.json", MODULES_DIR),
        ("*/set.json", DATA_DIR / "texturesets"),
    ):
        if not directory.exists():
            continue
        for path in directory.glob(pattern):
            try:
                stamps.append(path.stat().st_mtime)
            except OSError:
                continue
    return max(stamps) if stamps else 0.0


def ensure_preview(module_id: str) -> Path:
    """返回模块预览 GLB 路径；缓存缺失或过期时调用 Blender 重新生成。"""
    if not is_valid_module(module_id):
        raise FileNotFoundError(f"未知模块：{module_id}")

    target = PREVIEWS_DIR / f"{module_id}.glb"
    with _lock:
        if target.exists() and target.stat().st_mtime >= _source_stamp():
            return target

        PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp.glb")
        if temp.exists():
            temp.unlink()

        cmd = [
            str(BLENDER_EXE),
            "-b",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(GENERATOR_ENTRY),
            "--",
            "--module",
            module_id,
            "--module-out",
            str(temp),
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=PREVIEW_TIMEOUT_SECONDS,
            creationflags=CREATE_NO_WINDOW,
        )
        if completed.returncode != 0 or not temp.exists():
            tail = (completed.stdout or "").strip().splitlines()[-6:]
            raise RuntimeError("；".join(tail) or f"Blender 退出码 {completed.returncode}")

        temp.replace(target)
        return target
