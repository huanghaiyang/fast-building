"""按命名约定把已有建筑拆解为可复用模块，并输出模块描述符。

约定（与文档、模块库一致）：
- 集合命名 ``MOD_<category>_<name>``，一个集合即一个模块；
- 空物体命名 ``SOCK_<type>_<name>``，局部 -Y 为法线方向、+Z 为上；
- 网格对象自定义属性 ``slot``（材质槽名）与 ``tile_m``（贴图密度）；
- 对象名以 ``_L0`` / ``_L1`` 结尾视为同一模块的 LOD 层级。

用法：
    blender.exe -b --factory-startup --python generator/decompose.py -- \
        --source building.blend --out data/modules
支持 .blend 与 .glb（.glb 导入后集合信息会丢失，仅按对象坐标聚合）。

该脚本不做几何语义理解，只负责“按约定切分 + 生成描述符”，
后续可在 Blender 中继续编辑并保存为独立 .blend 资产。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VALID_CATEGORIES = {"wall", "slab", "roof", "opening", "stair", "balcony"}
LOD_PATTERN = re.compile(r"^(.*)_L(\d)$")


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = argv[1:]
    parser = argparse.ArgumentParser(description="按约定拆解建筑为模块")
    parser.add_argument("--source", required=True, help="输入 .blend 或 .glb")
    parser.add_argument("--out", default=str(ROOT / "data" / "modules"), help="描述符输出目录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的模块描述符")
    return parser.parse_args(argv)


def load_source(path: Path) -> None:
    import bpy

    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))


def world_bounds(objects: list) -> tuple[list[float], list[float]]:
    from mathutils import Vector

    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            for axis in range(3):
                minimum[axis] = min(minimum[axis], point[axis])
                maximum[axis] = max(maximum[axis], point[axis])
    if minimum[0] == float("inf"):
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    return minimum, maximum


def read_sockets(objects: list, origin: list[float]) -> list[dict]:
    from mathutils import Vector

    sockets: list[dict] = []
    for obj in objects:
        if obj.type != "EMPTY" or not obj.name.startswith("SOCK_"):
            continue
        parts = obj.name.split("_", 2)
        socket_type = parts[1] if len(parts) > 1 else "attach"
        socket_name = parts[2] if len(parts) > 2 else obj.name
        matrix = obj.matrix_world
        location = matrix.translation
        normal = matrix.to_3x3() @ Vector((0.0, -1.0, 0.0))
        up = matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))
        sockets.append(
            {
                "name": socket_name,
                "type": socket_type,
                "pos": [round(location[i] - origin[i], 4) for i in range(3)],
                "normal": [round(component, 4) for component in normal.normalized()],
                "up": [round(component, 4) for component in up.normalized()],
            }
        )
    return sockets


def read_slots(objects: list) -> list[dict]:
    slots: dict[str, float] = {}
    for obj in objects:
        if obj.type != "MESH":
            continue
        slot = obj.get("slot")
        if isinstance(slot, str) and slot:
            tile = obj.get("tile_m", 2.0)
            try:
                slots[slot] = float(tile)
            except (TypeError, ValueError):
                slots[slot] = 2.0
    if not slots:
        slots["facade"] = 2.0
    return [{"name": name, "texset": None, "tile_m": tile} for name, tile in slots.items()]


def read_lods(objects: list) -> tuple[list[dict], int]:
    levels: set[int] = set()
    for obj in objects:
        match = LOD_PATTERN.match(obj.name)
        if match:
            levels.add(int(match.group(2)))
    if not levels:
        levels = {0}
    return [{"level": level, "ratio": 1.0} for level in sorted(levels)], len(levels)


def check_uv_density(objects: list) -> list[str]:
    """粗检 UV 密度是否与 tile_m 匹配，偏差超过 10% 时给出告警。"""
    warnings: list[str] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        tile = obj.get("tile_m")
        if not isinstance(tile, (int, float)) or not obj.data.uv_layers:
            continue
        layer = obj.data.uv_layers.active
        if layer is None:
            continue
        us = [loop.uv[0] for loop in layer.data]
        vs = [loop.uv[1] for loop in layer.data]
        if not us:
            continue
        dims = obj.dimensions
        span_u = dims.x / float(tile) if float(tile) > 0 else 0
        span_v = dims.z / float(tile) if float(tile) > 0 else 0
        if span_u > 0 and abs((max(us) - min(us)) - span_u) > max(0.1, span_u * 0.1):
            warnings.append(
                f"{obj.name}: U 方向 UV 跨度 {max(us) - min(us):.2f} 与尺寸/tile_m={span_u:.2f} 偏差较大"
            )
        if span_v > 0 and abs((max(vs) - min(vs)) - span_v) > max(0.1, span_v * 0.1):
            warnings.append(
                f"{obj.name}: V 方向 UV 跨度 {max(vs) - min(vs):.2f} 与尺寸/tile_m={span_v:.2f} 偏差较大"
            )
    return warnings


def decompose(source: Path, out_dir: Path, overwrite: bool) -> int:
    import bpy

    if not source.exists():
        print(f"@@ERROR 源文件不存在: {source}")
        return 2
    load_source(source)

    targets = []
    for collection in bpy.data.collections:
        if collection.name.startswith("MOD_"):
            targets.append((collection.name, list(collection.all_objects)))
    # .glb 导入后没有集合命名，退化为按场景对象生成单个模块
    if not targets:
        targets = [("MOD_misc_imported", [obj for obj in bpy.context.scene.objects if obj.type in ("MESH", "EMPTY")])]

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    warnings: list[str] = []

    for collection_name, objects in targets:
        if not any(obj.type == "MESH" for obj in objects):
            continue
        parts = collection_name.split("_", 2)
        category = parts[1] if len(parts) > 1 else "misc"
        if category not in VALID_CATEGORIES:
            category = "misc"
        module_id = collection_name[4:].lower() if collection_name.startswith("MOD_") else "imported"
        target = out_dir / f"{module_id}.json"
        if target.exists() and not overwrite:
            print(f"跳过已存在模块: {target.name}")
            continue

        bounds_min, bounds_max = world_bounds(objects)
        size = [round(bounds_max[i] - bounds_min[i], 4) for i in range(3)]
        lods, _ = read_lods(objects)
        descriptor = {
            "id": module_id,
            "name": module_id,
            "version": 1,
            "category": category,
            "description": f"由 {source.name} 拆解生成",
            "tags": ["imported", collection_name],
            "units": "m",
            "bbox": {"min": [0.0, 0.0, 0.0], "max": size},
            "geom": {"type": "imported"},
            "sockets": read_sockets(objects, bounds_min),
            "slots": read_slots(objects),
            "lod": lods,
            "source": {"blend": source.name, "collection": collection_name},
            "decomposed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        target.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(target.name)

        for message in check_uv_density(objects):
            warnings.append(f"{collection_name} / {message}")

    print(f"@@DECOMPOSE 写出 {len(written)} 个模块: {', '.join(written) if written else '-'}")
    for warning in warnings:
        print(f"@@WARN {warning}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return decompose(Path(args.source).resolve(), Path(args.out).resolve(), args.overwrite)
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f"@@ERROR {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
