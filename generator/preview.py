"""单模块三维预览。

为模块库中的每个模块生成一份可独立查看的示例几何：
- 取该模块最具代表性的尺寸与形态，而不是整栋建筑；
- 复用装配阶段同一批几何函数，保证预览与实际生成结果一致；
- 贴图集从本地已安装的套件中按类别挑选，没有贴图时退化为纯色材质。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

from . import quality
from .assemble import create_object, ensure_collection, reset_scene
from .geom.arch import add_opening_pane, arch_strips, round_arch_strips
from .geom.balcony import build_balcony
from .geom.barn import build_barn_door
from .geom.chimney import build_chimney
from .geom.dormer import build_gable_dormer
from .geom.jetty import build_jetty_skirt
from .geom.logwall import build_log_wall
from .geom.parapet import build_crenellated_parapet
from .geom.plinth import build_plinth
from .geom.porch import build_thatch_porch
from .geom.props import build_street_props
from .geom.roof import build_flat_roof, build_gable_roof
from .geom.shopfront import build_shop_window
from .geom.slab import build_slab
from .geom.slate_roof import build_slate_roof
from .geom.stable import build_stable_bay
from .geom.stair import build_straight_stair
from .geom.thatch import build_thatch_roof
from .geom.timber import build_timber_frame
from .geom.wall_panel import Opening, build_wall_panel
from .geom.watermill import build_water_wheel
from .material.pbr import MaterialLibrary
from .meshkit import MeshBuilder
from .schema import SLAB_THICKNESS, WALL_THICKNESS

WALL_W = 2.8
WALL_H = 2.7
ROOF_W = 3.2
ROOF_D = 2.6

# (几何, 位置) 或 (几何, 位置, 绕 Z 旋转角度)
PreviewPart = (
    tuple[MeshBuilder, tuple[float, float, float]]
    | tuple[MeshBuilder, tuple[float, float, float], float]
)


def _available_sets(data_dir: Path) -> list[str]:
    directory = data_dir / "texturesets"
    if not directory.exists():
        return []
    return sorted(path.parent.name for path in directory.glob("*/set.json"))


def _pick(sets: list[str], keywords: tuple[str, ...], fallback: str) -> str:
    for keyword in keywords:
        for set_id in sets:
            if keyword.lower() in set_id.lower():
                return set_id
    return fallback


def _preview_material(data_dir: Path) -> MaterialLibrary:
    """按类别挑选贴图集，构造与正式生成一致的材质库。"""
    sets = _available_sets(data_dir)
    facade = _pick(sets, ("brick", "plaster", "stone", "rock"), sets[0] if sets else "")

    def pick(preferred: str, keywords: tuple[str, ...], fallback: str) -> str:
        """优先使用专为构件准备的贴图集，缺失时按关键字回退。"""
        if preferred in sets:
            return preferred
        return _pick(sets, keywords, fallback)

    # 优先用与街市风格一致的 CC0 实拍贴图，让模块缩略图与实际生成保持同一套材质
    style = {
        "palette": {
            "facade": facade,
            "trim": pick("timber_oak", ("timber", "wood", "plank"), facade),
            "roof": pick("RoofingTiles013A", ("roof", "shingle"), facade),
            "log": pick("Wood092", ("log", "wood", "timber"), facade),
            "thatch": pick("thatch_straw", ("thatch", "straw"), facade),
            "stone": pick("stone_rubble", ("stone", "rock"), facade),
            "door": pick("Planks039", ("plank", "wood", "timber"), facade),
        }
    }
    return MaterialLibrary(data_dir, facade, style)


def _window_opening(width: float, height: float, kind: str = "window") -> Opening:
    if kind == "door":
        return Opening(width * 0.5 - 0.55, width * 0.5 + 0.55, 0.0, 2.2, "door")
    return Opening(width * 0.5 - 0.6, width * 0.5 + 0.6, 0.85, 2.35, "window")


def _wall_builders(
    tiles: dict[str, float],
    kind: str = "window",
    arched: bool = False,
    timber: bool = False,
) -> list[tuple[MeshBuilder, tuple[float, float, float]]]:
    opening = _window_opening(WALL_W, WALL_H, kind)
    openings = [opening]
    if arched:
        strips: list[Opening] = []
        for item in openings:
            strips.extend(arch_strips(item))
        wall = build_wall_panel(WALL_W, WALL_H, WALL_THICKNESS, strips, tiles, glazing=False)
        for item in openings:
            add_opening_pane(wall, item, WALL_THICKNESS, arched=True)
    else:
        wall = build_wall_panel(WALL_W, WALL_H, WALL_THICKNESS, openings, tiles)

    base = (-WALL_W * 0.5, 0.0, 0.0)
    result: list[PreviewPart] = [(wall, base)]
    if timber:
        result.append((build_timber_frame(WALL_W, WALL_H, openings, tiles), base))
    return result


def _module_builders(module_id: str, tiles: dict[str, float]) -> list[PreviewPart]:
    if module_id == "wall_basic":
        return _wall_builders(tiles)
    if module_id == "wall_timber_frame":
        return _wall_builders(tiles, timber=True)
    if module_id == "opening_window":
        return _wall_builders(tiles, kind="window")
    if module_id == "opening_door":
        return _wall_builders(tiles, kind="door")
    if module_id == "opening_arch_window":
        return _wall_builders(tiles, kind="window", arched=True)
    if module_id == "opening_arch_door":
        return _wall_builders(tiles, kind="door", arched=True)
    if module_id == "slab_floor":
        slab = build_slab(ROOF_W, ROOF_D, 0.0, SLAB_THICKNESS, tiles)
        return [(slab, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "stair_straight":
        stair, _ = build_straight_stair(0.0, 0.0, 1.1, 2.8, 2.4, 0.0, tiles)
        return [(stair, (-0.55, -1.2, 0.0))]
    if module_id == "balcony_basic":
        balcony = build_balcony(0.0, 2.8, 0.0, 0.0, 1.1, tiles)
        return [(balcony, (-1.4, 0.55, 0.0))]
    if module_id == "roof_flat":
        roof = build_flat_roof(ROOF_W, ROOF_D, 0.0, 0.35, 0.22, tiles)
        return [(roof, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "roof_gable":
        roof = build_gable_roof(ROOF_W, ROOF_D, 0.0, 35.0, 0.35, 0.2, tiles)
        return [(roof, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "roof_crenellation":
        roof = build_flat_roof(ROOF_W, ROOF_D, 0.0, 0.35, 0.22, tiles)
        parapet = build_crenellated_parapet(ROOF_W, ROOF_D, 0.22, tiles)
        offset = (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0)
        return [(roof, offset), (parapet, offset)]
    if module_id == "dormer_gable":
        dormer = build_gable_dormer(1.05, 1.35, 1.5, tiles)
        # 窗体朝 +X，绕 Z 旋转 -90° 使其朝向 -Y，与其他模块的 3/4 视角一致
        return [(dormer, (0.0, -0.75, 0.0), -math.pi / 2)]
    if module_id == "chimney_stack":
        chimney = build_chimney(0.9, 0.62, 2.6, tiles)
        return [(chimney, (0.0, 0.0, 0.0))]
    if module_id == "wall_log_stack":
        openings = [Opening(WALL_W * 0.5 - 0.45, WALL_W * 0.5 + 0.45, 1.3, 2.05, "window")]
        wall = build_log_wall(
            WALL_W, WALL_H, openings, tiles, protrude_left=0.24, protrude_right=0.24
        )
        return [(wall, (-WALL_W * 0.5, 0.0, 0.0))]
    if module_id == "roof_thatch_gable":
        roof = build_thatch_roof(ROOF_W, ROOF_D, 0.0, 40.0, 0.55, 0.3, tiles)
        return [(roof, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "base_stone_plinth":
        plinth = build_plinth(
            ROOF_W, ROOF_D, 0.40, 0.45, 0.40, tiles, [(1.15, 2.05)], (0.95, 2.25)
        )
        return [(plinth, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "porch_thatch_canopy":
        porch = build_thatch_porch(2.2, 1.3, 0.68, 2.2, tiles)
        return [(porch, (0.0, 0.7, 0.0))]
    if module_id == "chimney_stone_stack":
        chimney = build_chimney(0.7, 0.62, 2.6, tiles, "stone")
        return [(chimney, (0.0, 0.0, 0.0))]
    # ---------------------------------------------------------------- 街市构件
    if module_id == "roof_slate_curved":
        roof = build_slate_roof(
            ROOF_W, ROOF_D, 0.0, 46.0, 0.36, 0.18, tiles, seed=7, curve=0.55
        )
        return [(roof, (-ROOF_W * 0.5, -ROOF_D * 0.5, 0.0))]
    if module_id == "opening_shop_books":
        opening = Opening(0.30, 2.80, 0.62, 2.52, "window")
        window = build_shop_window(
            opening, WALL_THICKNESS, tiles, kind="books", seed=7, rows=3
        )
        return [(window, (-1.55, 0.0, 0.0))]
    if module_id == "opening_shop_goods":
        opening = Opening(0.28, 2.32, 0.55, 2.22, "window")
        window = build_shop_window(
            opening, WALL_THICKNESS, tiles, kind="goods", seed=9, glazed=False, rows=2
        )
        return [(window, (-1.30, 0.0, 0.0))]
    if module_id == "opening_barn_door":
        return [(build_barn_door(2.4, 3.05, tiles, seed=5), (-1.2, 0.0, 0.0))]
    if module_id == "wall_stable_bay":
        opening = Opening(0.32, 2.38, 0.42, 2.76, "window")
        wall = build_wall_panel(
            2.7, 3.0, WALL_THICKNESS, round_arch_strips(opening), tiles, glazing=False
        )
        base = (-1.35, 0.0, 0.0)
        return [(wall, base), (build_stable_bay(2.7, 3.0, opening, tiles, seed=5), base)]
    if module_id == "wall_jetty_skirt":
        return [(build_jetty_skirt(3.2, 2.8, 0.3, tiles), (-1.6, -1.4, 0.95))]
    if module_id == "misc_market_props":
        props = build_street_props(4.0, 0.0, tiles, seed=11, kind="mixed")
        return [(props, (-2.0, 0.0, 0.0))]
    if module_id == "misc_water_wheel":
        wheel = build_water_wheel(tiles, 1.6, 0.55, paddles=20, spokes=8)
        return [(wheel, (0.0, 0.0, 1.6))]
    # 未知模块退化为标准墙板，保证接口始终有可用预览
    return _wall_builders(tiles)


def build_module_preview(
    module_id: str, data_dir: Path
) -> tuple[list[bpy.types.Object], dict]:
    """清空场景并生成单模块预览，返回对象列表与统计信息。"""
    reset_scene()
    collection = ensure_collection()
    mat_lib = _preview_material(data_dir)
    tiles = mat_lib.tiles
    # 模块预览与正式生成保持一致的着色质量
    quality.configure(True, 1)

    objects: list[bpy.types.Object] = []
    for index, part in enumerate(_module_builders(module_id, tiles)):
        builder, location = part[0], part[1]
        rotation = part[2] if len(part) > 2 else 0.0
        objects.append(
            create_object(
                builder,
                f"{module_id}_{index}",
                mat_lib,
                collection,
                location,
                rotation,
            )
        )

    tris = sum(
        len(polygon.vertices) - 2 for obj in objects for polygon in obj.data.polygons
    )
    stats = {
        "module": module_id,
        "objects": len(objects),
        "tris": tris,
        "textures": mat_lib.texture_summary(),
    }

    # 同时写出元数据，便于排查预览使用的贴图
    meta_path = data_dir / "previews" / f"{module_id}.json"
    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return objects, stats
