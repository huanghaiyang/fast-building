"""Blender 后台生成入口。

调用方式：
    blender.exe -b --factory-startup --python-exit-code 1 \
        --python generator/entry.py -- --job data/jobs/<id>/in.json

输出协议（stdout 标记行，后端据此更新任务进度）：
    @@STAGE <stage> <0..1>
    @@STATS <json>
    @@DONE <glb 绝对路径>
    @@ERROR <message>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def safe_print(text: str) -> None:
    """兼容 Windows 控制台编码：编码失败时降级为 ASCII。"""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"), flush=True)


def emit(marker: str, *parts: object) -> None:
    safe_print("@@" + marker + (" " + " ".join(str(p) for p in parts) if parts else ""))


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = argv[1:]
    parser = argparse.ArgumentParser(description="Fast Building generator")
    parser.add_argument("--job", help="任务输入 JSON 的绝对路径")
    parser.add_argument("--module", help="生成单个模块的三维预览")
    parser.add_argument("--module-out", help="模块预览 GLB 的输出路径")
    parser.add_argument("--smoke", action="store_true", help="生成测试立方体，用于连通性自检")
    return parser.parse_args(argv)


def run_smoke(job_path: Path | None) -> int:
    import bpy

    from generator.assemble import reset_scene
    from generator.exporter import export_glb

    reset_scene()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    out_dir = (job_path.parent / "out") if job_path else (Path.cwd() / "out")
    glb = export_glb(out_dir / "model.glb")
    emit("STATS", json.dumps({"smoke": True}))
    emit("DONE", glb)
    return 0


def run_job(job_path: Path) -> int:
    from generator.assemble import build_building, reset_scene
    from generator.exporter import export_glb
    from generator.schema import Spec

    if not job_path.exists():
        raise FileNotFoundError(f"任务文件不存在: {job_path}")

    spec_dict = json.loads(job_path.read_text(encoding="utf-8"))
    spec = Spec.from_dict(spec_dict)
    out_dir = job_path.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    emit("STAGE", "init", "0.05")
    reset_scene()

    emit("STAGE", "modules", "0.15")
    started = time.perf_counter()
    objects, stats, mat_lib = build_building(spec, ROOT / "data")
    build_seconds = time.perf_counter() - started

    emit("STAGE", "export", "0.80")
    glb = export_glb(out_dir / "model.glb")

    stats["seconds"] = round(build_seconds, 2)
    stats["glb_bytes"] = glb.stat().st_size if glb.exists() else 0
    stats["objects"] = len(objects)
    emit("STATS", json.dumps(stats, ensure_ascii=False))

    meta = {
        "spec": spec_dict,
        "style": spec.style,
        "textures": mat_lib.texture_summary(),
        "stats": stats,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    emit("DONE", glb)
    return 0


def run_module_preview(module_id: str, out_path: Path) -> int:
    import json as json_module

    from generator.exporter import export_glb
    from generator.preview import build_module_preview

    emit("STAGE", "modules", "0.15")
    started = time.perf_counter()
    _, stats = build_module_preview(module_id, ROOT / "data")

    emit("STAGE", "export", "0.80")
    glb = export_glb(out_path)
    stats["seconds"] = round(time.perf_counter() - started, 2)
    stats["glb_bytes"] = glb.stat().st_size if glb.exists() else 0
    emit("STATS", json_module.dumps(stats, ensure_ascii=False))
    emit("DONE", glb)
    return 0


def main() -> int:
    args = parse_args()
    job_path = Path(args.job).resolve() if args.job else None
    try:
        if args.smoke:
            return run_smoke(job_path)
        if args.module:
            out_path = (
                Path(args.module_out).resolve()
                if args.module_out
                else (ROOT / "data" / "previews" / f"{args.module}.glb")
            )
            return run_module_preview(args.module, out_path)
        if job_path is None:
            emit("ERROR", "--job is required")
            return 2
        return run_job(job_path)
    except Exception as exc:  # noqa: BLE001 - 统一上报给后端
        traceback.print_exc()
        emit("ERROR", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
