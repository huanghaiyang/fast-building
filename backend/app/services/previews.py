"""模块预览资源（GLB 与缩略图）的生成、缓存与后台预热。

服务启动后由一个后台线程扫描 ``data/modules``，为每个模块生成：
- ``data/previews/<id>.glb``：用于卡片展开后的三维预览；
- ``data/previews/<id>.png``：用于模块列表的缩略图。

之后新增的模块会在下一轮扫描时自动补齐；generator 源码、模块描述符或
贴图集发生变化时，相关缓存自动重建。
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
PREVIEW_TIMEOUT_SECONDS = 180
PREWARM_INTERVAL_SECONDS = 4.0
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_MODULE_ID = re.compile(r"^[A-Za-z0-9_]+$")
_lock = threading.Lock()

_prewarm_stop = threading.Event()
_prewarm_thread: threading.Thread | None = None


def is_valid_module(module_id: str) -> bool:
    if not _MODULE_ID.match(module_id):
        return False
    return (MODULES_DIR / f"{module_id}.json").exists()


def preview_glb_path(module_id: str) -> Path:
    return PREVIEWS_DIR / f"{module_id}.glb"


def preview_png_path(module_id: str) -> Path:
    return PREVIEWS_DIR / f"{module_id}.png"


def _global_stamp() -> float:
    """generator 源码与贴图集的最后修改时间，影响全部模块。"""
    stamps: list[float] = []
    for pattern, directory in (
        ("**/*.py", GENERATOR_DIR),
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


def _module_stamp(module_id: str) -> float:
    stamp = _global_stamp()
    descriptor = MODULES_DIR / f"{module_id}.json"
    try:
        stamp = max(stamp, descriptor.stat().st_mtime)
    except OSError:
        pass
    return stamp


def _is_fresh(glb: Path, png: Path, stamp: float) -> bool:
    try:
        return glb.exists() and png.exists() and glb.stat().st_mtime >= stamp and png.stat().st_mtime >= stamp
    except OSError:
        return False


def ensure_assets(module_id: str) -> tuple[Path, Path]:
    """确保模块的 GLB 与缩略图均已生成，返回两者路径。"""
    if not is_valid_module(module_id):
        raise FileNotFoundError(f"未知模块：{module_id}")

    glb = preview_glb_path(module_id)
    png = preview_png_path(module_id)
    stamp = _module_stamp(module_id)

    with _lock:
        if _is_fresh(glb, png, stamp):
            return glb, png

        PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        temp_glb = glb.with_name(f"{module_id}.tmp.glb")
        temp_png = png.with_name(f"{module_id}.tmp.png")
        for temp in (temp_glb, temp_png):
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
            str(temp_glb),
            "--thumb-out",
            str(temp_png),
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
        if completed.returncode != 0 or not temp_glb.exists() or not temp_png.exists():
            tail = (completed.stdout or "").strip().splitlines()[-6:]
            raise RuntimeError("；".join(tail) or f"Blender 退出码 {completed.returncode}")

        temp_glb.replace(glb)
        temp_png.replace(png)
        return glb, png


def ensure_preview(module_id: str) -> Path:
    return ensure_assets(module_id)[0]


def ensure_thumbnail(module_id: str) -> Path:
    return ensure_assets(module_id)[1]


# --------------------------------------------------------------------------- 后台预热
def _pending_modules() -> list[str]:
    ids: list[str] = []
    if not MODULES_DIR.exists():
        return ids
    for path in sorted(MODULES_DIR.glob("*.json")):
        module_id = path.stem
        if not _MODULE_ID.match(module_id):
            continue
        if not _is_fresh(preview_glb_path(module_id), preview_png_path(module_id), _module_stamp(module_id)):
            ids.append(module_id)
    return ids


def _prewarm_loop() -> None:
    while not _prewarm_stop.is_set():
        try:
            for module_id in _pending_modules():
                if _prewarm_stop.is_set():
                    return
                try:
                    ensure_assets(module_id)
                except Exception:  # noqa: BLE001 - 单个模块失败不应中断预热
                    continue
        except Exception:  # noqa: BLE001 - 扫描异常时等待下一轮
            pass
        _prewarm_stop.wait(PREWARM_INTERVAL_SECONDS)


def start_prewarm() -> None:
    global _prewarm_thread
    if _prewarm_thread and _prewarm_thread.is_alive():
        return
    _prewarm_stop.clear()
    _prewarm_thread = threading.Thread(target=_prewarm_loop, name="module-preview-prewarm", daemon=True)
    _prewarm_thread.start()


def stop_prewarm() -> None:
    _prewarm_stop.set()
    thread = _prewarm_thread
    if thread and thread.is_alive():
        thread.join(timeout=2.0)
