"""批量重建模块预览（GLB + 缩略图）。

用途：调整了 generator/preview.py 或 thumbnail.py 的造型/材质/渲染风格后，
一次性把 data/previews 下所有历史模块重新生成，避免在浏览器里逐个点开。

用法（Blender 无头，需在项目根目录执行）：
    D:\\blender\\blender.exe -b --factory-startup --python tools/rebuild_module_previews.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator.exporter import export_glb  # noqa: E402
from generator.preview import build_module_preview  # noqa: E402
from generator.thumbnail import render_thumbnail  # noqa: E402


def main() -> int:
    data_dir = ROOT / "data"
    module_ids = sorted(path.stem for path in (data_dir / "modules").glob("*.json"))
    if not module_ids:
        print("未找到模块描述文件", flush=True)
        return 1

    out_dir = data_dir / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    done: list[str] = []

    for index, module_id in enumerate(module_ids):
        build_module_preview(module_id, data_dir)
        export_glb(out_dir / f"{module_id}.glb")
        render_thumbnail(out_dir / f"{module_id}.png")
        done.append(module_id)
        print(f"[{index + 1}/{len(module_ids)}] {module_id}", flush=True)

    elapsed = round(time.perf_counter() - started, 1)
    print(
        "REBUILD_DONE "
        + json.dumps({"count": len(done), "seconds": elapsed}, ensure_ascii=False),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
