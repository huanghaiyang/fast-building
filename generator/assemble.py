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

from . import quality
from .geom.arch import add_opening_pane, add_round_arch_pane, arch_strips, round_arch_strips
from .geom.balcony import build_balcony
from .geom.bellcote import build_bellcote
from .geom.burn import build_burnt_roof, build_scorch_patches
from .geom.buttress import build_buttress, build_finial_cross, build_pinnacle
from .geom.chapel import build_bell_tower, build_broken_gable, build_nave_roof
from .geom.chimney import build_chimney
from .geom.cottage import build_door_dressing, build_gable_window, build_window_boxes
from .geom.dormer import build_gable_dormer
from .geom.foliage import build_vegetation
from .geom.gable_frame import build_gable_frame
from .geom.gallery import build_gallery
from .geom.lancet import build_lancet, build_rose_window
from .geom.logwall import build_log_wall
from .geom.parapet import build_crenellated_parapet
from .geom.plinth import build_plinth
from .geom.porch import build_thatch_porch
from .geom.ridge import build_ridge_cap
from .geom.roof import build_flat_roof, build_gable_roof, build_open_roof_frame
from .geom.ruin import build_collapsed_ruin, build_leaning_planks, build_rubble
from .geom.sign import build_shop_sign
from .geom.slab import build_slab
from .geom.stair import build_straight_stair
from .geom.thatch import build_thatch_roof
from .geom.timber import build_timber_frame
from .geom.wall_panel import Opening, build_wall_panel, ruin_top_profile
from .geom.watchtower import (
    HOARDING_FLOOR_T,
    LOOKOUT_INSET,
    LOOKOUT_WALL_H,
    build_hoarding,
    build_lookout,
    build_stepped_base,
)
from .geom.window_trim import build_opening_trims
from .material.pbr import MaterialLibrary
from .meshkit import MeshBuilder
from .schema import SLAB_THICKNESS, WALL_THICKNESS, Spec

LOG_CORNER = 0.24

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
    quality.apply(obj)
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
        # 0.10 m 是箭孔这类窄洞的下限，再窄墙板会退化成细碎条带
        if x1 - x0 < 0.10:
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
        # 样式可覆盖门洞尺寸（石屋废墟的半圆券门比默认门窗更宽更高）
        door_w = min(float(style.get("door_w", spec.openings.door_w)), span * 0.6)
        door_h = min(float(style.get("door_h", spec.openings.door_h)), wall_height - 0.18)
        door_x0 = (span - door_w) * 0.5
        door_x1 = (span + door_w) * 0.5
        openings = [Opening(door_x0, door_x1, 0.0, door_h, "door")]
        # 门两侧对称小窗，避免开间中间只有一个门、两侧大片空墙
        if int(style.get("door_windows", 0)) >= 2:
            win_w = min(float(style.get("door_window_w", 0.8)), door_w)
            sill = float(style.get("door_window_sill", 1.15))
            win_h = min(
                float(style.get("door_window_h", 0.95)), wall_height - sill - 0.25
            )
            gap = 0.30
            if win_h >= 0.4:
                if door_x0 - gap - win_w > 0.12:
                    openings.append(
                        Opening(
                            door_x0 - gap - win_w,
                            door_x0 - gap,
                            sill,
                            sill + win_h,
                            "window",
                        )
                    )
                if door_x1 + gap + win_w < span - 0.12:
                    openings.append(
                        Opening(
                            door_x1 + gap,
                            door_x1 + gap + win_w,
                            sill,
                            sill + win_h,
                            "window",
                        )
                    )
        return openings
    count = int(style.get("windows_per_bay", 1))
    return _window_openings(count, span, wall_height, spec, rng)


def _side_openings(
    span: float,
    wall_height: float,
    floor_index: int,
    spec: Spec,
    style: dict,
) -> list[Opening]:
    rng = random.Random(f"{spec.seed}:side:{floor_index}")
    # 礼拜堂这类纵向长侧墙可以排多扇窗，默认仍是一扇
    count = max(1, int(style.get("side_windows", 1)))
    return _window_openings(count, span, wall_height, spec, rng)


def _wall_panel(
    width: float,
    height: float,
    openings: list[Opening],
    tiles: dict[str, float],
    arched: bool,
    edge_slot: str = "trim",
    scorch: bool = False,
    top_profile: list[tuple[float, float, float]] | None = None,
    round_arch: bool = False,
    glazed: bool = True,
    window_slot: str = "glass",
) -> MeshBuilder:
    """生成墙板；拱形模式下用矩形带逼近拱头，并单独补玻璃/门扇面片。"""
    if not arched:
        builder = build_wall_panel(
            width,
            height,
            WALL_THICKNESS,
            openings,
            tiles,
            glazing=glazed,
            edge_slot=edge_slot,
            top_profile=top_profile,
            window_slot=window_slot,
        )
    else:
        strips: list[Opening] = []
        for op in openings:
            strips.extend(round_arch_strips(op) if round_arch else arch_strips(op))
        builder = build_wall_panel(
            width,
            height,
            WALL_THICKNESS,
            strips,
            tiles,
            glazing=False,
            edge_slot=edge_slot,
            top_profile=top_profile,
        )
        if glazed:
            for op in openings:
                if round_arch:
                    add_round_arch_pane(builder, op, WALL_THICKNESS, slot=window_slot)
                else:
                    add_opening_pane(
                        builder, op, WALL_THICKNESS, arched=True, slot=window_slot
                    )
    if scorch:
        # 每面墙用尺寸与洞口位置生成不同的炭化斑块
        key = int((width * 31 + height * 17 + sum(op.x0 for op in openings) * 13) * 100)
        build_scorch_patches(builder, width, height, openings, WALL_THICKNESS, key)
    return builder


def _wall_builder(
    width: float,
    height: float,
    openings: list[Opening],
    tiles: dict[str, float],
    arched: bool,
    medieval,
    left_end: bool,
    right_end: bool,
    edge_slot: str = "trim",
    top_profile: list[tuple[float, float, float]] | None = None,
    glazed: bool = True,
    window_slot: str = "glass",
) -> MeshBuilder:
    """按开关选择原木墙或普通墙板；只有建筑外墙端才让圆木出挑。"""
    if medieval.log_walls:
        return build_log_wall(
            width,
            height,
            openings,
            tiles,
            protrude_left=LOG_CORNER if left_end else 0.0,
            protrude_right=LOG_CORNER if right_end else 0.0,
        )
    return _wall_panel(
        width,
        height,
        openings,
        tiles,
        arched,
        edge_slot,
        scorch=medieval.burnt,
        top_profile=top_profile,
        round_arch=medieval.round_arch,
        glazed=glazed,
        window_slot=window_slot,
    )


def _ground_door(spec: Spec, style: dict) -> tuple[float, float] | None:
    """首层中心开间的门洞中心与宽度；不设门时返回 None。"""
    if not style.get("door", True):
        return None
    bay_width = spec.width / spec.bays
    door_w = min(float(style.get("door_w", spec.openings.door_w)), bay_width * 0.6)
    return (spec.bays // 2 + 0.5) * bay_width, door_w


# --------------------------------------------------------------------------- 主体装配
def build_building(
    spec: Spec, data_dir: Path
) -> tuple[list[bpy.types.Object], dict, MaterialLibrary]:
    style = load_style(data_dir, spec.style)
    mat_lib = MaterialLibrary(data_dir, spec.textureset, style)
    tiles = mat_lib.tiles
    collection = ensure_collection()
    # 着色与细分策略必须在建对象之前生效，create_object 会逐件套用
    quality.configure(spec.smooth, spec.subdiv)
    medieval = spec.medieval
    arched = medieval.arch_openings or medieval.round_arch
    glazed = bool(style.get("glazed", True))
    # 暖色玻璃：农舍风格把窗户换成暖黄面片，读成屋里点着灯
    window_slot = str(style.get("window_slot", "glass"))
    # 尖拱券石环：给尖拱门窗补一圈贯通墙厚的券石，盖住条带近似的台阶
    arch_ring = bool(style.get("pointed_arch_ring", False))
    trim_slot = style.get("trim_slot", "trim")
    slab_slot = style.get("slab_slot", "trim")
    trim_openings = (
        medieval.timber_frame or medieval.thatch_roof or bool(style.get("opening_trims"))
    )
    # 中世纪悬挑楼层：二层起每层向外挑出 0.3 m
    jetty_step = 0.3 if medieval.jetty else 0.0
    # 半木构墙面上用木板填充部分开间（灰泥 + 木板混排）
    plank_panels = bool(style.get("plank_panels"))

    root = bpy.data.objects.new("BUILDING", None)
    collection.objects.link(root)

    objects: list[bpy.types.Object] = []
    wall_height = spec.floor_height - SLAB_THICKNESS

    # 塌毁石屋：整栋退化为残墙 + 瓦砾 + 焦木，不再生成楼板、勒脚与屋顶
    if medieval.collapsed:
        ruin_height = spec.floor_height - 0.15
        ruin_door = _ground_door(spec, style)
        parts = build_collapsed_ruin(
            spec.width,
            spec.depth,
            ruin_height,
            WALL_THICKNESS,
            tiles,
            spec.seed,
            ruin_door,
            spec.openings.door_h,
        )
        for name, (mesh, location, rotation) in parts.items():
            objects.append(
                create_object(mesh, name, mat_lib, collection, location, rotation)
            )
        for obj in objects:
            obj.parent = root
        stats = _collect_stats(objects, mat_lib)
        return objects, stats, mat_lib

    for floor in range(spec.floors):
        base_z = floor * spec.floor_height
        wall_z = base_z + SLAB_THICKNESS
        ext = jetty_step * floor
        floor_w = spec.width + 2 * ext
        floor_d = spec.depth + 2 * ext
        bay_width = floor_w / spec.bays
        side_length = floor_d - 2 * WALL_THICKNESS

        # 楼板
        slab = build_slab(
            floor_w, floor_d, base_z, SLAB_THICKNESS, tiles, slot=slab_slot
        )
        objects.append(
            create_object(slab, f"slab_f{floor}", mat_lib, collection, (-ext, -ext, 0.0))
        )

        # 前后立面：按开间切分
        for bay in range(spec.bays):
            x0 = bay * bay_width - ext
            is_center = bay == spec.bays // 2

            front_ops = _bay_openings(bay_width, wall_height, floor, "front", is_center, spec, style)
            front = _wall_builder(
                bay_width,
                wall_height,
                front_ops,
                tiles,
                arched,
                medieval,
                bay == 0,
                bay == spec.bays - 1,
                edge_slot=trim_slot,
                glazed=glazed,
                window_slot=window_slot,
            )
            objects.append(
                create_object(front, f"wall_front_f{floor}_b{bay}", mat_lib, collection, (x0, -ext, wall_z), 0.0)
            )
            if trim_openings:
                trims = build_opening_trims(
                    front_ops,
                    WALL_THICKNESS,
                    tiles,
                    slot=trim_slot,
                    arched=arched,
                    round_arch=medieval.round_arch,
                    arch_ring=arch_ring,
                )
                objects.append(
                    create_object(
                        trims,
                        f"trim_front_f{floor}_b{bay}",
                        mat_lib,
                        collection,
                        (x0, -ext, wall_z),
                        0.0,
                    )
                )
            if medieval.timber_frame and not medieval.log_walls:
                frame = build_timber_frame(
                    bay_width, wall_height, front_ops, tiles, plank_panel=plank_panels
                )
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
            # 窗台花箱：只在首层正立面，且该开间确实有窗
            if (
                medieval.window_boxes
                and floor == 0
                and any(op.kind == "window" for op in front_ops)
            ):
                boxes = build_window_boxes(front_ops, tiles, seed=spec.seed)
                objects.append(
                    create_object(
                        boxes,
                        f"window_boxes_front_b{bay}",
                        mat_lib,
                        collection,
                        (x0, -ext, wall_z),
                        0.0,
                    )
                )

            back_ops = _bay_openings(bay_width, wall_height, floor, "back", False, spec, style)
            back = _wall_builder(
                bay_width,
                wall_height,
                back_ops,
                tiles,
                arched,
                medieval,
                bay == spec.bays - 1,
                bay == 0,
                edge_slot=trim_slot,
                glazed=glazed,
                window_slot=window_slot,
            )
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
            if trim_openings:
                trims = build_opening_trims(
                    back_ops,
                    WALL_THICKNESS,
                    tiles,
                    slot=trim_slot,
                    arched=arched,
                    round_arch=medieval.round_arch,
                    arch_ring=arch_ring,
                )
                objects.append(
                    create_object(
                        trims,
                        f"trim_back_f{floor}_b{bay}",
                        mat_lib,
                        collection,
                        (x0 + bay_width, spec.depth + ext, wall_z),
                        math.pi,
                    )
                )
            if medieval.timber_frame and not medieval.log_walls:
                frame = build_timber_frame(
                    bay_width, wall_height, back_ops, tiles, plank_panel=plank_panels
                )
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
            ruin_top = medieval.wall_ruin and floor == spec.floors - 1
            left_ops = _side_openings(side_length, wall_height, floor, spec, style)
            left_profile = (
                ruin_top_profile(side_length, wall_height, left_ops, f"{spec.seed}:left:{floor}")
                if ruin_top
                else None
            )
            left = _wall_builder(
                side_length,
                wall_height,
                left_ops,
                tiles,
                arched,
                medieval,
                True,
                True,
                edge_slot=trim_slot,
                top_profile=left_profile,
                glazed=glazed,
                window_slot=window_slot,
            )
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
            if trim_openings:
                trims = build_opening_trims(
                    left_ops,
                    WALL_THICKNESS,
                    tiles,
                    slot=trim_slot,
                    arched=arched,
                    round_arch=medieval.round_arch,
                    arch_ring=arch_ring,
                )
                objects.append(
                    create_object(
                        trims,
                        f"trim_left_f{floor}",
                        mat_lib,
                        collection,
                        (-ext, spec.depth + ext - WALL_THICKNESS, wall_z),
                        -math.pi / 2,
                    )
                )
            if medieval.timber_frame and not medieval.log_walls:
                frame = build_timber_frame(
                    side_length, wall_height, left_ops, tiles, plank_panel=plank_panels
                )
                objects.append(
                    create_object(
                        frame,
                        f"timber_left_f{floor}",
                        mat_lib,
                        collection,
                        (-ext, spec.depth + ext - WALL_THICKNESS, wall_z),
                        -math.pi / 2,
                    )
                )

            right_ops = _side_openings(side_length, wall_height, floor, spec, style)
            right_profile = (
                ruin_top_profile(side_length, wall_height, right_ops, f"{spec.seed}:right:{floor}")
                if ruin_top
                else None
            )
            right = _wall_builder(
                side_length,
                wall_height,
                right_ops,
                tiles,
                arched,
                medieval,
                True,
                True,
                edge_slot=trim_slot,
                top_profile=right_profile,
                glazed=glazed,
                window_slot=window_slot,
            )
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
            if trim_openings:
                trims = build_opening_trims(
                    right_ops,
                    WALL_THICKNESS,
                    tiles,
                    slot=trim_slot,
                    arched=arched,
                    round_arch=medieval.round_arch,
                    arch_ring=arch_ring,
                )
                objects.append(
                    create_object(
                        trims,
                        f"trim_right_f{floor}",
                        mat_lib,
                        collection,
                        (spec.width + ext, -ext + WALL_THICKNESS, wall_z),
                        math.pi / 2,
                    )
                )
            if medieval.timber_frame and not medieval.log_walls:
                frame = build_timber_frame(
                    side_length, wall_height, right_ops, tiles, plank_panel=plank_panels
                )
                objects.append(
                    create_object(
                        frame,
                        f"timber_right_f{floor}",
                        mat_lib,
                        collection,
                        (spec.width + ext, -ext + WALL_THICKNESS, wall_z),
                        math.pi / 2,
                    )
                )

        # 哥特石扶壁：前后立面按开间分界，侧墙落在四角与跨中
        if medieval.buttresses:
            pier = build_buttress(wall_height, tiles)
            corner_piers = bool(style.get("buttress_corners"))
            # (名称, x, y, 绕 z 的旋转)；转角墩只在需要时补
            placements: list[tuple[str, float, float, float]] = []
            front_xs = [bay * bay_width for bay in range(1, spec.bays)]
            if corner_piers:
                front_xs = [0.0, *front_xs, floor_w]
            for index, px in enumerate(front_xs):
                placements.append((f"front_f{floor}_{index}", px - ext, -ext, 0.0))
                placements.append(
                    (f"back_f{floor}_{index}", px - ext, spec.depth + ext, math.pi)
                )

            side_positions = [0.3, side_length - 0.3]
            if side_length > 5.4:
                side_positions[1:1] = [side_length * 0.36, side_length * 0.64]
            if corner_piers and side_length > 4.0:
                # 转角已由前后立面的转角墩承担，侧墙只留跨中，避免角部叠成一堆
                side_positions = side_positions[1:-1]
            for index, u in enumerate(side_positions):
                placements.append(
                    (
                        f"left_f{floor}_{index}",
                        -ext,
                        spec.depth + ext - WALL_THICKNESS - u,
                        -math.pi / 2,
                    )
                )
                placements.append(
                    (
                        f"right_f{floor}_{index}",
                        spec.width + ext,
                        -ext + WALL_THICKNESS + u,
                        math.pi / 2,
                    )
                )

            for name, px, py, rot in placements:
                objects.append(
                    create_object(
                        pier, f"buttress_{name}", mat_lib, collection, (px, py, wall_z), rot
                    )
                )

            # 扶壁顶上的小尖塔：只做到顶层，转角墩与跨中墩都立一枚
            if medieval.pinnacles and floor == spec.floors - 1:
                pinnacle = build_pinnacle(
                    tiles, height=max(1.05, min(1.85, wall_height * 0.32))
                )
                for name, px, py, rot in placements:
                    objects.append(
                        create_object(
                            pinnacle,
                            f"pinnacle_{name}",
                            mat_lib,
                            collection,
                            (px, py, wall_z + wall_height),
                            rot,
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

        # 环绕木廊（半木构客栈）：二层沿前、左、右三面外挑一圈木廊
        if medieval.gallery and floor == 1:
            gallery = build_gallery(floor_w, floor_d, SLAB_THICKNESS, tiles)
            objects.append(
                create_object(gallery, "gallery", mat_lib, collection, (-ext, -ext, base_z))
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

    # 毛石勒脚与茅草门廊（乡土构件）
    door = _ground_door(spec, style)

    # 悬挑店招：挂在门旁，朝向正面
    if medieval.shop_sign and door is not None:
        door_cx, door_w = door
        sign_x = door_cx + door_w * 0.5 + 1.0
        if sign_x > spec.width - 0.8:
            sign_x = door_cx - door_w * 0.5 - 1.0
        sign_x = min(max(sign_x, 0.7), spec.width - 0.7)
        sign_z = min(2.55, spec.floor_height - 0.55)
        sign = build_shop_sign(tiles)
        objects.append(
            create_object(sign, "shop_sign", mat_lib, collection, (sign_x, 0.0, sign_z))
        )
    if medieval.stepped_base:
        base = build_stepped_base(spec.width, spec.depth, 1.3, tiles)
        objects.append(create_object(base, "stepped_base", mat_lib, collection))

    if medieval.stone_plinth:
        gaps: list[tuple[float, float]] = []
        step = None
        if door is not None:
            door_cx, door_w = door
            gaps.append((door_cx - door_w * 0.5 - 0.18, door_cx + door_w * 0.5 + 0.18))
            # 有门廊时由门廊石台代替台阶，避免两级台基互相穿插
            if not medieval.porch:
                step = (door_cx - door_w * 0.5 - 0.35, door_cx + door_w * 0.5 + 0.35)
        plinth = build_plinth(spec.width, spec.depth, 0.40, 0.45, 0.40, tiles, gaps, step)
        objects.append(create_object(plinth, "plinth_stone", mat_lib, collection))

    # 门口陈设：两侧石花盆 + 门旁暖光壁灯
    if medieval.door_dressing and door is not None:
        door_cx, door_w = door
        dressing = build_door_dressing(door_cx, door_w, tiles, seed=spec.seed)
        objects.append(create_object(dressing, "door_dressing", mat_lib, collection))

    if medieval.porch and door is not None:
        door_cx, door_w = door
        bay_width = spec.width / spec.bays
        porch_w = min(bay_width * 0.95, door_w + 1.9)
        # 檐口压到 2.15 m、抬高屋脊，避免门廊变成贴门的小帽子
        eave_h = min(2.15, wall_height - 0.55)
        porch = build_thatch_porch(porch_w, 1.5, 1.05, eave_h, tiles)
        objects.append(
            create_object(porch, "porch_thatch", mat_lib, collection, (door_cx, 0.0, 0.0))
        )

    # 常春藤与墙根花丛：只在乡土风格里开启
    if medieval.ivy:
        veg = build_vegetation(
            spec.width,
            spec.depth,
            spec.floors * spec.floor_height,
            spec.seed,
            door,
            ivy_coverage=medieval.ivy_coverage,
            ivy_height=medieval.ivy_height,
        )
        objects.append(create_object(veg, "vegetation", mat_lib, collection))

    # 塌落梁架：墙边斜靠的木板与地上的倒伏断板
    if medieval.collapsed_beams:
        planks = build_leaning_planks(
            spec.width,
            spec.depth,
            wall_height,
            tiles,
            spec.seed,
            door,
            slot="log",
        )
        objects.append(create_object(planks, "fallen_planks", mat_lib, collection))

    # 屋顶：按顶层（含悬挑）轮廓生成
    top_ext = jetty_step * (spec.floors - 1)
    roof_w = spec.width + 2 * top_ext
    roof_d = spec.depth + 2 * top_ext
    roof_z = spec.floors * spec.floor_height
    roof_top = roof_z + 0.22
    roof_half = (roof_w + 0.9) * 0.5
    roof_overhang = 0.45

    if medieval.lookout:
        # 石砌瞭望塔：塔身用木挑廊 + 木构瞭望棚收头，不再生成整栋坡屋顶
        if medieval.hoarding:
            hoarding = build_hoarding(spec.width, spec.depth, tiles)
            objects.append(
                create_object(hoarding, "hoarding", mat_lib, collection, (0.0, 0.0, roof_z))
            )
        cabin_z = roof_z + HOARDING_FLOOR_T
        cabin = build_lookout(spec.width, spec.depth, tiles)
        objects.append(
            create_object(cabin, "lookout", mat_lib, collection, (0.0, 0.0, cabin_z))
        )
        crown = build_gable_roof(
            spec.width - 2 * LOOKOUT_INSET,
            spec.depth - 2 * LOOKOUT_INSET,
            cabin_z + LOOKOUT_WALL_H + 0.12,
            spec.roof_pitch,
            0.30,
            0.14,
            tiles,
            gable_slot="log",
        )
        objects.append(
            create_object(
                crown,
                "lookout_roof",
                mat_lib,
                collection,
                (LOOKOUT_INSET, LOOKOUT_INSET, 0.0),
            )
        )
        roof_top = cabin_z + LOOKOUT_WALL_H + 0.26
        roof_half = (spec.width + 0.6) * 0.5
    elif spec.roof == "flat":
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
    elif medieval.nave_roof:
        # 废墟教堂：屋脊改沿长轴，西端立方形钟塔，东端作出崩缺的山墙。
        # 屋面只留檐口与屋脊附近的零星石板，椽条与檩条整排外露。
        nave_half = (roof_d + 2.0 * 0.45) * 0.5
        nave_rise = math.tan(math.radians(spec.roof_pitch)) * nave_half
        ridge_z = roof_z + 0.22 + nave_rise

        tower_w = min(max(spec.width * 0.27, 2.8), 4.2)
        tower_h = ridge_z + spec.floor_height * 0.85
        tower = build_bell_tower(tower_w, roof_d + 0.14, tower_h, tiles, spec.seed)
        objects.append(
            create_object(
                tower, "bell_tower", mat_lib, collection, (-top_ext - 0.07, -top_ext - 0.07, 0.0)
            )
        )

        roof = build_nave_roof(
            -top_ext - 0.07 + tower_w - 0.12,
            -top_ext + roof_w + 0.35,
            roof_d,
            roof_z,
            spec.roof_pitch,
            0.45,
            0.18,
            tiles,
            ruin=0.82,
            seed=spec.seed,
            timber_slot="log",
        )
        objects.append(create_object(roof, "roof", mat_lib, collection))

        gable = build_broken_gable(
            roof_d, nave_half, nave_rise, 0.22, 0.30, tiles, seed=spec.seed
        )
        objects.append(
            create_object(
                gable,
                "gable_east",
                mat_lib,
                collection,
                (-top_ext + roof_w, -top_ext, roof_z),
                math.pi / 2,
            )
        )
        if style.get("gable_lancet"):
            lancet = build_lancet(tiles, 0.62, 1.45, slot=trim_slot)
            objects.append(
                create_object(
                    lancet,
                    "gable_lancet_east",
                    mat_lib,
                    collection,
                    (-top_ext + roof_w, -top_ext + roof_d * 0.5, roof_top + nave_rise * 0.28),
                    math.pi / 2,
                )
            )

        # 墙脚与室内散落的碎石、断板
        rubble = build_rubble(spec.width, spec.depth, roof_z, tiles, spec.seed, scale=1.5)
        objects.append(create_object(rubble, "rubble", mat_lib, collection))

        roof_top = roof_z + 0.18
        roof_half = nave_half
    elif medieval.collapsed_beams:
        # 圆拱石屋废墟：屋面石板全部塌落，只剩破损山墙与脊梁、檐檩、椽条
        roof = build_open_roof_frame(
            roof_w,
            roof_d,
            roof_z,
            spec.roof_pitch,
            roof_overhang,
            tiles,
            seed=spec.seed,
            gable_slot="facade",
            timber_slot="log",
        )
        objects.append(
            create_object(roof, "roof_frame", mat_lib, collection, (-top_ext, -top_ext, 0.0))
        )
        roof_top = roof_z + 0.20
        roof_half = (roof_w + 2.0 * roof_overhang) * 0.5
    else:
        if medieval.burnt:
            # 烧毁：一坡残存茅草、一坡残存石瓦，上部缺失，露出炭黑椽条与山墙木架
            overhang = 0.5
            roof = build_burnt_roof(
                roof_w,
                roof_d,
                roof_z,
                spec.roof_pitch,
                overhang,
                tiles,
                seed=spec.seed,
            )
            roof_half = (roof_w + 2.0 * overhang) * 0.5
            roof_top = roof_z + math.tan(math.radians(spec.roof_pitch)) * roof_half
            roof_overhang = overhang
        elif medieval.thatch_roof:
            # 厚茅草：默认 0.30 m 草层 + 0.55 m 出檐，童话农舍可在样式里加厚加大
            thickness = float(style.get("thatch_thickness", 0.30))
            overhang = float(style.get("thatch_overhang", 0.55))
            # 半木构的山墙不做成草面，而是贴外墙材质的三角墙 + 外露木架
            framed_gable = medieval.timber_frame and not medieval.log_walls
            gable_window = (
                None
                if framed_gable
                else (roof_w * 0.5, roof_z + 1.05, 0.62, 0.5)
            )
            roof = build_thatch_roof(
                roof_w,
                roof_d,
                roof_z,
                spec.roof_pitch,
                overhang,
                thickness,
                tiles,
                gable_slot="facade" if framed_gable else "thatch",
                gable_window=gable_window,
                gable_overhang=0.02 if framed_gable else 0.18,
                fringe=0.16 if framed_gable else 0.10,
                thatch_ridge=framed_gable,
                rake_roll=thickness * 0.42 if framed_gable else 0.0,
                shingle_band=(0.33, 0.60) if medieval.shingle_band else None,
            )
            roof_top = roof_z + thickness
            roof_half = (roof_w + 2.0 * overhang) * 0.5
            roof_overhang = overhang

            if framed_gable:
                half = roof_w * 0.5 + overhang
                rise = math.tan(math.radians(spec.roof_pitch)) * half + thickness
                gable = build_gable_frame(2.0 * half, rise, tiles)
                gable_x = -top_ext + roof_w * 0.5 - half
                objects.append(
                    create_object(
                        gable, "gable_frame_front", mat_lib, collection, (gable_x, -top_ext - 0.02, roof_z)
                    )
                )
                objects.append(
                    create_object(
                        gable,
                        "gable_frame_back",
                        mat_lib,
                        collection,
                        (gable_x + 2.0 * half, -top_ext + roof_d + 0.02, roof_z),
                        math.pi,
                    )
                )
                # 山墙小窗＋窗下花箱：贴在木架三角墙上
                if medieval.gable_window:
                    window = build_gable_window(tiles, seed=spec.seed)
                    objects.append(
                        create_object(
                            window,
                            "gable_window",
                            mat_lib,
                            collection,
                            (
                                roof_w * 0.5 - top_ext,
                                -top_ext - 0.13,
                                roof_z + rise * 0.30,
                            ),
                        )
                    )
        else:
            roof = build_gable_roof(
                roof_w,
                roof_d,
                roof_z,
                spec.roof_pitch,
                0.45,
                0.22,
                tiles,
                ruin=0.6 if medieval.ruined_roof else 0.0,
                seed=spec.seed,
                gable_ruin=0.55 if medieval.wall_ruin else 0.0,
            )
        objects.append(
            create_object(roof, "roof", mat_lib, collection, (-top_ext, -top_ext, 0.0))
        )

        # 悬山收头：屋脊压梁探出山墙，山墙两侧补木封檐板
        if medieval.ridge_cap and not medieval.burnt:
            cap = build_ridge_cap(roof_w, roof_d, roof_z, spec.roof_pitch, 0.45, 0.22, tiles)
            objects.append(
                create_object(cap, "ridge_cap", mat_lib, collection, (-top_ext, -top_ext, 0.0))
            )

        # 半木构山墙：三角墙面外加外露木架
        if style.get("gable_frame") and not medieval.thatch_roof and not medieval.burnt:
            gable_half = roof_w * 0.5 + 0.45
            frame_rise = math.tan(math.radians(spec.roof_pitch)) * gable_half
            frame = build_gable_frame(2.0 * gable_half, frame_rise, tiles)
            gable_x = -top_ext + roof_w * 0.5 - gable_half
            objects.append(
                create_object(
                    frame,
                    "gable_frame_front",
                    mat_lib,
                    collection,
                    (gable_x, -top_ext - 0.47, roof_z + 0.22),
                )
            )
            objects.append(
                create_object(
                    frame,
                    "gable_frame_back",
                    mat_lib,
                    collection,
                    (gable_x + 2.0 * gable_half, -top_ext + roof_d + 0.47, roof_z + 0.22),
                    math.pi,
                )
            )

        if style.get("gable_lancet") and not medieval.thatch_roof and not medieval.burnt:
            gable_rise = math.tan(math.radians(spec.roof_pitch)) * roof_half
            lancet_w = min(1.1, max(0.7, roof_w * 0.085))
            lancet_h = lancet_w * 2.3
            if gable_rise > lancet_h + 1.0:
                lancet = build_lancet(tiles, lancet_w, lancet_h, slot=trim_slot)
                lancet_z = roof_top + (gable_rise - lancet_h) * 0.28
                # 山墙面即屋顶的前后轮廓面，比墙体再挑出 0.45 m 檐口
                gable_front_y = -top_ext - 0.45
                gable_back_y = -top_ext + roof_d + 0.45
                objects.append(
                    create_object(
                        lancet,
                        "gable_lancet_front",
                        mat_lib,
                        collection,
                        (roof_w * 0.5 - top_ext, gable_front_y, lancet_z),
                    )
                )
                objects.append(
                    create_object(
                        lancet,
                        "gable_lancet_back",
                        mat_lib,
                        collection,
                        (roof_w * 0.5 - top_ext, gable_back_y, lancet_z),
                        math.pi,
                    )
                )

        # 山墙玫瑰窗与山尖石十字：完好哥特礼拜堂的正立面
        if medieval.rose_window and spec.roof == "gable" and not (
            medieval.thatch_roof
            or medieval.burnt
            or medieval.nave_roof
            or medieval.collapsed_beams
        ):
            gable_rise = math.tan(math.radians(spec.roof_pitch)) * roof_half
            radius = min(roof_w * 0.16, gable_rise * 0.30)
            if gable_rise > 2.2 and radius > 0.5:
                rose = build_rose_window(tiles, radius, slot=trim_slot)
                rose_z = roof_top + gable_rise * 0.44
                # 山墙面即屋顶的前后轮廓面，比墙体再挑出 0.45 m 檐口
                gable_front_y = -top_ext - 0.45
                gable_back_y = -top_ext + roof_d + 0.45
                objects.append(
                    create_object(
                        rose,
                        "rose_window_front",
                        mat_lib,
                        collection,
                        (roof_w * 0.5 - top_ext, gable_front_y, rose_z),
                    )
                )
                objects.append(
                    create_object(
                        rose,
                        "rose_window_back",
                        mat_lib,
                        collection,
                        (roof_w * 0.5 - top_ext, gable_back_y, rose_z),
                        math.pi,
                    )
                )
                if medieval.pinnacles:
                    cross = build_finial_cross(
                        tiles, height=max(0.5, min(0.9, gable_rise * 0.13)), slot=trim_slot
                    )
                    apex_z = roof_top + gable_rise
                    objects.append(
                        create_object(
                            cross,
                            "gable_cross_front",
                            mat_lib,
                            collection,
                            (roof_w * 0.5 - top_ext, gable_front_y + 0.05, apex_z - 0.05),
                        )
                    )
                    objects.append(
                        create_object(
                            cross,
                            "gable_cross_back",
                            mat_lib,
                            collection,
                            (roof_w * 0.5 - top_ext, gable_back_y - 0.05, apex_z - 0.05),
                            math.pi,
                        )
                    )

        # 石钟塔：立在屋脊靠前的位置，塔脚埋进屋面
        if medieval.bellcote and spec.roof == "gable" and not medieval.thatch_roof:
            bell_w, bell_t = 1.5, 0.45
            ridge_z = roof_z + 0.22 + math.tan(math.radians(spec.roof_pitch)) * roof_half
            bell = build_bellcote(tiles)
            objects.append(
                create_object(
                    bell,
                    "bellcote",
                    mat_lib,
                    collection,
                    (
                        roof_w * 0.5 - bell_w * 0.5 - top_ext,
                        -top_ext + roof_d * 0.22 - bell_t * 0.5,
                        ridge_z - 0.62,
                    ),
                )
            )

        # 老虎窗：左右两坡对称布置，滑杆数值为每坡数量
        # 茅草屋顶的老虎窗要用草顶，并嵌进坡面中段的石瓦腰带里
        if medieval.dormers > 0:
            count = min(medieval.dormers, 4)
            thatch = medieval.thatch_roof
            size = (1.25, 1.25, 1.35) if thatch else (1.05, 1.35, 1.5)
            body = build_gable_dormer(
                size[0],
                size[1],
                size[2],
                tiles,
                roof_slot="thatch" if thatch else "roof",
                body_slot="trim" if thatch else "facade",
            )
            pitch = math.tan(math.radians(spec.roof_pitch))
            # 沿坡面向内收，使窗体嵌入坡面而不是挂在檐口
            inset = roof_half * 0.34 if thatch else 0.9
            surface = roof_top + inset * pitch
            z_base = surface - (0.30 if thatch else 0.25)
            for index in range(count):
                y_center = roof_d * (index + 1) / (count + 1)
                objects.append(
                    create_object(
                        body,
                        f"dormer_right_{index}",
                        mat_lib,
                        collection,
                        (roof_w + roof_overhang - inset - top_ext, y_center - top_ext, z_base),
                        0.0,
                    )
                )
                objects.append(
                    create_object(
                        body,
                        f"dormer_left_{index}",
                        mat_lib,
                        collection,
                        (-roof_overhang + inset - top_ext, y_center - top_ext, z_base),
                        math.pi,
                    )
                )

    # 烟囱：穿透屋顶并高出屋面约 1.5 m；多烟囱骑在屋脊上分列两端
    if medieval.chimney:
        pitch_tan = math.tan(math.radians(spec.roof_pitch))
        ridge_z = roof_top + roof_half * pitch_tan
        count = min(max(1, medieval.chimney_count), 4)
        spots: list[tuple[float, float, float]] = []
        if spec.roof == "flat":
            spots.append((roof_w * 0.72, roof_d * 0.68, roof_top))
        elif count <= 1:
            cx = roof_w * 0.5
            chim_x = cx + roof_half * 0.38
            spots.append(
                (chim_x, roof_d * 0.68, roof_top + (roof_half - abs(chim_x - cx)) * pitch_tan)
            )
        else:
            for index in range(count):
                # 骑脊的烟囱靠向两端山墙
                frac = 0.18 + 0.64 * index / (count - 1)
                spots.append((roof_w * 0.5, roof_d * frac, ridge_z))
        # 茅草农舍使用毛石烟囱，与勒脚呼应
        slot = "stone" if (medieval.thatch_roof or medieval.stone_plinth) else "trim"
        chimney = build_chimney(0.78, 0.62, 2.1, tiles, slot)
        for index, (chim_x, chim_y, surface) in enumerate(spots):
            objects.append(
                create_object(
                    chimney,
                    "chimney" if len(spots) == 1 else f"chimney_{index}",
                    mat_lib,
                    collection,
                    (chim_x - top_ext, chim_y - top_ext, surface - 1.1),
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

    bpy.context.view_layer.update()
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
