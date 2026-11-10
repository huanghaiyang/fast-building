"""单模块三维预览。

为模块库中的每个模块生成一份可独立查看的示例几何：
- 取该模块最具代表性的尺寸与形态，而不是整栋建筑；
- 复用装配阶段同一批几何函数，保证预览与实际生成结果一致；
- 贴图集从本地已安装的套件中按类别挑选，没有贴图时退化为纯色材质。
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy

from .assemble import create_object, ensure_collection, reset_scene
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
from .schema import SLAB_THICKNESS, WALL_THICKNESS

WALL_W = 2.8
WALL_H = 2.7
ROOF_W = 3.2
ROOF_D = 2.6


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
    style = {
        "palette": {
            "trim": _pick(sets, ("plank", "wood", "timber"), facade),
            "roof": _pick(sets, ("roof", "shingle"), facade),
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
    result: list[tuple[MeshBuilder, tuple[float, float, float]]] = [(wall, base)]
    if timber:
        result.append((build_timber_frame(WALL_W, WALL_H, openings, tiles), base))
    return result


def _module_builders(
    module_id: str, tiles: dict[str, float]
) -> list[tuple[MeshBuilder, tuple[float, float, float]]]:
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
        return [(dormer, (0.75, 0.0, 0.0))]
    if module_id == "chimney_stack":
        chimney = build_chimney(0.9, 0.62, 2.6, tiles)
        return [(chimney, (0.0, 0.0, 0.0))]
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

    objects: list[bpy.types.Object] = []
    for index, (builder, location) in enumerate(_module_builders(module_id, tiles)):
        objects.append(
            create_object(
                builder,
                f"{module_id}_{index}",
                mat_lib,
                collection,
                location,
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
