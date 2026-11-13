"""风格预设多视角渲染（可视化自检工具）。

用途：不启动 Web 平台，直接在 Blender 里按某个风格预设生成整栋建筑，
再用 EEVEE 渲染前视 / 3/4 / 侧视多张图，用于和参考图对比、调参。

用法：
    blender.exe -b --factory-startup --python-exit-code 1 \
        --python tools/render_style.py -- --style watermill_house \
        --out .run/qa/watermill --width 1024 --height 768

参数全部可选；``--style`` 缺省时渲染中世纪木筋屋。footprint 未给出的字段
回退到风格预设里的 ``preset``，再回退到 ``generator.schema.Spec`` 的默认值。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIEWS = {
    "front": ((0.0, -1.0, 0.42), "正面"),
    "quarter": ((0.86, -1.28, 0.58), "3/4"),
    "quarter_back": ((-0.9, 1.2, 0.55), "3/4 背面"),
    "side": ((-1.0, 0.05, 0.40), "侧面"),
    "back": ((0.0, 1.0, 0.42), "背面"),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else argv[1:]
    parser = argparse.ArgumentParser(description="按风格渲染多视角预览")
    parser.add_argument("--style", default="medieval_timber_pbr")
    parser.add_argument("--textureset", default="")
    parser.add_argument("--out", default=str(ROOT / ".run" / "qa" / "style"))
    parser.add_argument("--width", type=float, default=0.0)
    parser.add_argument("--depth", type=float, default=0.0)
    parser.add_argument("--bays", type=int, default=0)
    parser.add_argument("--floors", type=int, default=0)
    parser.add_argument("--floor-height", type=float, default=0.0)
    parser.add_argument("--roof-pitch", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--views", default="front,quarter,side")
    parser.add_argument("--res", type=int, default=900)
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--blend-out", default="", help="额外保存 .blend 的路径")
    parser.add_argument("--frame", default="", help="只框住名字以该前缀开头的对象，用于看细节")
    return parser.parse_args(argv)


def build_spec(args: argparse.Namespace):
    from generator.schema import Spec

    style_path = ROOT / "data" / "styles" / f"{args.style}.json"
    style = json.loads(style_path.read_text(encoding="utf-8"))
    preset = style.get("preset") or {}
    data = dict(preset)
    data.setdefault("style", args.style)
    data.setdefault("textureset", args.textureset or "Plaster002")
    # 构型开关写在风格里，装配阶段从 Spec.medieval 读，这里合并一次
    data["medieval"] = dict(style.get("medieval") or {})
    data["seed"] = args.seed
    data["balcony"] = False
    data.setdefault("smooth", True)
    data.setdefault("subdiv", 1)
    for key, value in (
        ("width", args.width),
        ("depth", args.depth),
        ("bays", args.bays),
        ("floors", args.floors),
        ("floor_height", args.floor_height),
        ("roof_pitch", args.roof_pitch),
    ):
        if value:
            data[key] = value
    return Spec.from_dict(data)


def scene_bounds(prefix: str = ""):
    from mathutils import Vector
    import bpy

    low = Vector((1e18, 1e18, 1e18))
    high = Vector((-1e18, -1e18, -1e18))
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.name.startswith("QA_"):
            continue
        if prefix and not obj.name.startswith(prefix):
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            low = Vector((min(low[i], point[i]) for i in range(3)))
            high = Vector((max(high[i], point[i]) for i in range(3)))
    if low.x > 1e17:
        return Vector((0, 0, 0)), Vector((1, 1, 1))
    return low, high


def setup_world(sun_z: float) -> None:
    import bpy
    from mathutils import Vector

    world = bpy.data.worlds.new("QA_WORLD")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.62, 0.70, 0.82, 1.0)
        bg.inputs[1].default_value = 0.55
    bpy.context.scene.world = world

    sun_data = bpy.data.lights.new("QA_SUN", "SUN")
    sun_data.energy = 2.4
    sun_data.angle = math.radians(5.0)
    sun = bpy.data.objects.new("QA_SUN", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.location = (6.0, -8.0, sun_z + 14.0)
    sun.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))

    # 地面，便于判断体量与接地
    bpy.ops.mesh.primitive_plane_add(size=120.0, location=(0.0, 0.0, -0.01))
    ground = bpy.context.active_object
    ground.name = "QA_GROUND"
    mat = bpy.data.materials.new("QA_GROUND_MAT")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.42, 0.44, 0.40, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.92
    ground.data.materials.append(mat)


def eevee_engine() -> str:
    """Blender 4.2~5.x 的 EEVEE 引擎 id 改过两次，这里做一次兼容探测。"""
    import bpy

    available = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    for candidate in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        if candidate in available:
            return candidate
    return "CYCLES"


def render_view(
    name: str, direction, out_path: Path, res: int, samples: int, bounds=None
) -> None:
    import bpy
    from mathutils import Vector

    scene = bpy.context.scene
    low, high = bounds if bounds is not None else scene_bounds()
    center = (low + high) * 0.5
    size = high - low
    radius = max(size.length * 0.5, 0.5)

    camera_data = bpy.data.cameras.new(f"CAM_{name}")
    camera_data.lens = 52.0
    camera_data.sensor_width = 36.0
    camera = bpy.data.objects.new(f"CAM_{name}", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    fov_x = 2.0 * math.atan(camera_data.sensor_width / (2.0 * camera_data.lens))
    fov_y = 2.0 * math.atan(math.tan(fov_x * 0.5) * 0.75)
    distance = radius / math.sin(min(fov_x, fov_y) * 0.5) * 1.02
    offset = Vector(direction).normalized() * distance
    camera.location = center + offset
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.clip_start = 0.05
    camera_data.clip_end = distance * 20.0

    scene.render.engine = eevee_engine()
    scene.eevee.taa_render_samples = samples
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.render.resolution_x = res
    scene.render.resolution_y = int(res * 0.75)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera, do_unlink=True)


def main() -> int:
    args = parse_args()
    import bpy

    from generator.assemble import build_building, reset_scene

    spec = build_spec(args)
    reset_scene()
    objects, stats, mat_lib = build_building(spec, ROOT / "data")
    print("@@STATS", json.dumps(stats, ensure_ascii=False))
    low, high = scene_bounds()

    if args.blend_out:
        target = Path(args.blend_out).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(target))

    detail_bounds = (low, high)
    if args.frame:
        detail_bounds = scene_bounds(args.frame)
    setup_world(high.z)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for view in [item.strip() for item in args.views.split(",") if item.strip()]:
        direction, _label = VIEWS.get(view, VIEWS["quarter"])
        render_view(
            view,
            direction,
            out_dir / f"{args.style}_{view}.png",
            args.res,
            args.samples,
            bounds=detail_bounds,
        )
        print("@@VIEW", out_dir / f"{args.style}_{view}.png")
    print("@@DONE", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
