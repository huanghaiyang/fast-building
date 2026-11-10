"""参数化建筑装配。

输入 Spec，输出一组 Blender 对象（墙体、楼板、楼梯、阳台、屋顶）与统计信息。
所有几何均在 Python 中生成，不依赖 bpy.ops 的建模操作，保证后台模式下稳定。
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bmesh
import bpy

from .geom.arch import add_opening_pane, arch_strips
from .geom.balcony import build_balcony
from .geom.chimney import build_chimney
from .geom.dormer import build_gable_dormer
from .geom.parapet import build_crenellated_parapet
from .geom.roof import build_flat_roof, build_gable_roof
from .geom.slab import build_slab
from .geom.stair import build_straight_stair
from .geom.timber import build_timber_frame
from .geom.wall_panel import Opening, build_wall_panel
from .material.pbr import MaterialLibrary
from .meshkit import MeshBuilder
from .schema import SLAB_THICKNESS, WALL_THICKNESS, Spec

DEFAULT_STYLE = {
    "id": "default",
    "name": "默认风格",
    "window_w": 1.4,
    "window_h": 1.6,
    "sill_h": 0.9,
    "windows_per_bay": 1,
    "door": True,
    "balcony": True,
    "palette": {"trim": "concrete_gray", "roof": "roof_tile"},
}


def load_style(data_dir: Path, style_id: str) -> dict:
    style = dict(DEFAULT_STYLE)
    style["id"] = style_id
    path = data_dir / "styles" / f"{style_id}.json"
    if path.exists():
        try:
            style.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return style


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def ensure_collection(name: str = "BUILDING") -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def create_object(
    builder: MeshBuilder,
    name: str,
    mat_lib: MaterialLibrary,
    collection: bpy.types.Collection,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_z: float = 0.0,
) -> bpy.types.Object:
    """把 MeshBuilder 转成带 UV 与多材质的 Blender 对象。"""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(builder.verts, [], builder.faces)
    mesh.update()

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for face_index, polygon in enumerate(mesh.polygons):
        loop_uvs = builder.face_uvs[face_index]
        for k, loop_index in enumerate(polygon.loop_indices):
            uv_layer.data[loop_index].uv = loop_uvs[k]

    slot_order: list[str] = []
    for slot in builder.face_slots:
        if slot not in slot_order:
            slot_order.append(slot)
    for slot in slot_order:
        mesh.materials.append(mat_lib.get(slot))

    slot_index = {slot: index for index, slot in enumerate(slot_order)}
    for face_index, polygon in enumerate(mesh.polygons):
        polygon.material_index = slot_index[builder.face_slots[face_index]]

    # 统一法线朝向（每个构件都是封闭实体或双面片）
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler[2] = rotation_z
    collection.objects.link(obj)
    return obj


# --------------------------------------------------------------------------- 洞口规划
def _window_openings(
    count: int,
    span: float,
    wall_height: float,
    spec: Spec,
    rng: random.Random,
) -> list[Opening]:
    openings: list[Opening] = []
    if count <= 0:
        return openings
    width = min(spec.openings.window_w, span * 0.55)
    width *= rng.uniform(0.92, 1.06)
    height = min(spec.openings.window_h, wall_height - spec.openings.sill_h - 0.3)
    if height < 0.5:
        return openings

    slot = span / count
    for i in range(count):
        cx = slot * (i + 0.5)
        x0 = max(0.12, cx - width * 0.5)
        x1 = min(span - 0.12, cx + width * 0.5)
        if x1 - x0 < 0.35:
            continue
        openings.append(
            Opening(x0, x1, spec.openings.sill_h, spec.openings.sill_h + height, "window")
        )
    return openings


def _bay_openings(
    span: float,
    wall_height: float,
    floor_index: int,
    side: str,
    is_center: bool,
    spec: Spec,
    style: dict,
) -> list[Opening]:
    rng = random.Random(f"{spec.seed}:{side}:{floor_index}:{is_center}")
    if floor_index == 0 and side == "front" and is_center and style.get("door", True):
        door_w = min(spec.openings.door_w, span * 0.6)
        door_h = min(spec.openings.door_h, wall_height - 0.18)
        return [Opening((span - door_w) * 0.5, (span + door_w) * 0.5, 0.0, door_h, "door")]
    count = int(style.get("windows_per_bay", 1))
    return _window_openings(count, span, wall_height, spec, rng)


def _side_openings(span: float, wall_height: float, floor_index: int, spec: Spec) -> list[Opening]:
    rng = random.Random(f"{spec.seed}:side:{floor_index}")
    return _window_openings(1, span, wall_height, spec, rng)


def _wall_panel(
    width: float,
    height: float,
    openings: list[Opening],
    tiles: dict[str, float],
    arched: bool,
) -> MeshBuilder:
    """生成墙板；尖拱模式下用矩形带逼近拱头，并单独补玻璃/门扇面片。"""
    if not arched:
        return build_wall_panel(width, height, WALL_THICKNESS, openings, tiles)

    strips: list[Opening] = []
    for op in openings:
        strips.extend(arch_strips(op))
    builder = build_wall_panel(width, height, WALL_THICKNESS, strips, tiles, glazing=False)
    for op in openings:
        add_opening_pane(builder, op, WALL_THICKNESS, arched=True)
    return builder


# --------------------------------------------------------------------------- 主体装配
def build_building(
    spec: Spec, data_dir: Path
) -> tuple[list[bpy.types.Object], dict, MaterialLibrary]:
    style = load_style(data_dir, spec.style)
    mat_lib = MaterialLibrary(data_dir, spec.textureset, style)
    tiles = mat_lib.tiles
    collection = ensure_collection()
    medieval = spec.medieval
    arched = medieval.arch_openings
    # 中世纪悬挑楼层：二层起每层向外挑出 0.3 m
    jetty_step = 0.3 if medieval.jetty else 0.0

    root = bpy.data.objects.new("BUILDING", None)
    collection.objects.link(root)

    objects: list[bpy.types.Object] = []
    wall_height = spec.floor_height - SLAB_THICKNESS

    for floor in range(spec.floors):
        base_z = floor * spec.floor_height
        wall_z = base_z + SLAB_THICKNESS
        ext = jetty_step * floor
        floor_w = spec.width + 2 * ext
        floor_d = spec.depth + 2 * ext
        bay_width = floor_w / spec.bays
        side_length = floor_d - 2 * WALL_THICKNESS

        # 楼板
        slab = build_slab(floor_w, floor_d, base_z, SLAB_THICKNESS, tiles)
        objects.append(
            create_object(slab, f"slab_f{floor}", mat_lib, collection, (-ext, -ext, 0.0))
        )

        # 前后立面：按开间切分
        for bay in range(spec.bays):
            x0 = bay * bay_width - ext
            is_center = bay == spec.bays // 2

            front_ops = _bay_openings(bay_width, wall_height, floor, "front", is_center, spec, style)
            front = _wall_panel(bay_width, wall_height, front_ops, tiles, arched)
            objects.append(
                create_object(front, f"wall_front_f{floor}_b{bay}", mat_lib, collection, (x0, -ext, wall_z), 0.0)
            )
            if medieval.timber_frame:
                frame = build_timber_frame(bay_width, wall_height, front_ops, tiles)
                objects.append(
                    create_object(
                        frame,
                        f"timber_front_f{floor}_b{bay}",
                        mat_lib,
                        collection,
                        (x0, -ext, wall_z),
                        0.0,
                    )
                )

            back_ops = _bay_openings(bay_width, wall_height, floor, "back", False, spec, style)
            back = _wall_panel(bay_width, wall_height, back_ops, tiles, arched)
            objects.append(
                create_object(
                    back,
                    f"wall_back_f{floor}_b{bay}",
                    mat_lib,
                    collection,
                    (x0 + bay_width, spec.depth + ext, wall_z),
                    math.pi,
                )
            )
            if medieval.timber_frame:
                frame = build_timber_frame(bay_width, wall_height, back_ops, tiles)
                objects.append(
                    create_object(
                        frame,
                        f"timber_back_f{floor}_b{bay}",
                        mat_lib,
                        collection,
                        (x0 + bay_width, spec.depth + ext, wall_z),
                        math.pi,
                    )
                )

        # 左右侧墙：内缩出墙角，避免与前后面共面产生 z-fighting
        if side_length > 1.2:
            left_ops = _side_openings(side_length, wall_height, floor, spec)
            left = _wall_panel(side_length, wall_height, left_ops, tiles, arched)
            objects.append(
                create_object(
                    left,
                    f"wall_left_f{floor}",
                    mat_lib,
                    collection,
                    (-ext, spec.depth + ext - WALL_THICKNESS, wall_z),
                    -math.pi / 2,
                )
            )

            right_ops = _side_openings(side_length, wall_height, floor, spec)
            right = _wall_panel(side_length, wall_height, right_ops, tiles, arched)
            objects.append(
                create_object(
                    right,
                    f"wall_right_f{floor}",
                    mat_lib,
                    collection,
                    (spec.width + ext, -ext + WALL_THICKNESS, wall_z),
                    math.pi / 2,
                )
            )

        # 阳台（二层及以上）
        if floor >= 1 and spec.balcony and style.get("balcony", True):
            balcony_w = min(floor_w * 0.5, 4.5)
            bx0 = (floor_w - balcony_w) * 0.5
            balcony = build_balcony(bx0, bx0 + balcony_w, 0.0, base_z, 1.15, tiles)
            objects.append(
                create_object(balcony, f"balcony_f{floor}", mat_lib, collection, (-ext, -ext, 0.0))
            )

    # 室内直跑楼梯（一层到二层）
    if spec.floors >= 2:
        total_rise = spec.floor_height - SLAB_THICKNESS
        steps = max(4, int(round(total_rise / 0.18)))
        available = spec.depth - 2 * WALL_THICKNESS - 1.2
        total_run = max(1.2, min(available, steps * 0.27))
        if available > 1.2:
            stair_x = WALL_THICKNESS + 0.35
            stair_y = WALL_THICKNESS + 0.35
            stair, _ = build_straight_stair(
                stair_x,
                stair_y,
                1.2,
                total_rise,
                total_run,
                SLAB_THICKNESS,
                tiles,
            )
            objects.append(create_object(stair, "stairs_f0", mat_lib, collection))

    # 屋顶：按顶层（含悬挑）轮廓生成
    top_ext = jetty_step * (spec.floors - 1)
    roof_w = spec.width + 2 * top_ext
    roof_d = spec.depth + 2 * top_ext
    roof_z = spec.floors * spec.floor_height
    roof_top = roof_z + 0.22

    if spec.roof == "flat":
        roof = build_flat_roof(roof_w, roof_d, roof_z, 0.45, 0.28, tiles)
        objects.append(
            create_object(roof, "roof", mat_lib, collection, (-top_ext, -top_ext, 0.0))
        )
        roof_top = roof_z + 0.28
        if medieval.crenellation:
            parapet = build_crenellated_parapet(roof_w, roof_d, roof_top, tiles)
            objects.append(
                create_object(
                    parapet, "parapet_crenel", mat_lib, collection, (-top_ext, -top_ext, 0.0)
                )
            )
    else:
        roof = build_gable_roof(
            roof_w, roof_d, roof_z, spec.roof_pitch, 0.45, 0.22, tiles
        )
        objects.append(
            create_object(roof, "roof", mat_lib, collection, (-top_ext, -top_ext, 0.0))
        )

        # 老虎窗：左右两坡对称布置，滑杆数值为每坡数量
        if medieval.dormers > 0:
            count = min(medieval.dormers, 4)
            body = build_gable_dormer(1.05, 1.35, 1.5, tiles)
            pitch = math.tan(math.radians(spec.roof_pitch))
            # 沿坡面向内收 0.9 m，使窗体嵌入坡面而不是挂在檐口
            inset = 0.9
            surface = roof_top + inset * pitch
            z_base = surface - 0.25
            for index in range(count):
                y_center = roof_d * (index + 1) / (count + 1)
                objects.append(
                    create_object(
                        body,
                        f"dormer_right_{index}",
                        mat_lib,
                        collection,
                        (roof_w + 0.45 - inset - top_ext, y_center - top_ext, z_base),
                        0.0,
                    )
                )
                objects.append(
                    create_object(
                        body,
                        f"dormer_left_{index}",
                        mat_lib,
                        collection,
                        (-0.45 + inset - top_ext, y_center - top_ext, z_base),
                        math.pi,
                    )
                )

    # 烟囱：穿透屋顶并高出屋面约 1.5 m
    if medieval.chimney:
        if spec.roof == "flat":
            surface = roof_top
            chim_x = roof_w * 0.72
        else:
            half = (roof_w + 0.9) * 0.5
            cx = roof_w * 0.5
            chim_x = cx + half * 0.38
            surface = roof_top + (half - abs(chim_x - cx)) * math.tan(
                math.radians(spec.roof_pitch)
            )
        chimney = build_chimney(0.9, 0.62, 2.6, tiles)
        objects.append(
            create_object(
                chimney,
                "chimney",
                mat_lib,
                collection,
                (chim_x - top_ext, roof_d * 0.68 - top_ext, surface - 1.1),
            )
        )

    for obj in objects:
        obj.parent = root

    stats = _collect_stats(objects, mat_lib)
    return objects, stats, mat_lib


def _collect_stats(objects: list[bpy.types.Object], mat_lib: MaterialLibrary) -> dict:
    verts = 0
    tris = 0
    materials: set[str] = set()
    for obj in objects:
        mesh = obj.data
        verts += len(mesh.vertices)
        for polygon in mesh.polygons:
            tris += len(polygon.vertices) - 2
        for mat in mesh.materials:
            if mat is not None:
                materials.add(mat.name)

    bbox_min = [float("inf")] * 3
    bbox_max = [float("-inf")] * 3
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ __import__("mathutils").Vector(corner)
            for axis in range(3):
                bbox_min[axis] = min(bbox_min[axis], world[axis])
                bbox_max[axis] = max(bbox_max[axis], world[axis])

    return {
        "verts": verts,
        "tris": tris,
        "objects": len(objects),
        "materials": len(materials),
        "textures": mat_lib.texture_summary(),
        "bbox": {
            "min": [round(v, 3) for v in bbox_min],
            "max": [round(v, 3) for v in bbox_max],
        },
    }
