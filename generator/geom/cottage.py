"""农舍小陈设：窗台花箱、山墙小窗、门口花盆与门旁壁灯。

局部坐标与墙板一致：X 沿墙、Y=0 为外饰面（负方向朝外）、Z 自墙脚起算。
山墙小窗用贴面做法（山墙面在屋顶里，无法开洞）。
"""

from __future__ import annotations

import random

from ..meshkit import MeshBuilder
from .wall_panel import Opening

LEAF = "leaf"
FLOWER = "flower"
BOX_SLOT = "log"


def _blossom(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    cz: float,
    size: float,
    rnd: random.Random,
) -> None:
    """一小丛花：叶片团 + 两三枚花色小方块，读成圆润的花球。"""
    w = size * 0.5
    builder.add_box((cx - w, cy - w, cz), (cx + w, cy + w, cz + size * 0.75), LEAF)
    for _ in range(3):
        fx = cx + rnd.uniform(-w * 0.8, w * 0.8)
        fy = cy + rnd.uniform(-w * 0.8, w * 0.8)
        fz = cz + size * 0.55 + rnd.uniform(0.0, size * 0.3)
        s = size * 0.20
        builder.add_box((fx - s, fy - s, fz - s), (fx + s, fy + s, fz + s), FLOWER)


def build_window_boxes(
    openings: list[Opening],
    tiles: dict[str, float],
    seed: int = 42,
) -> MeshBuilder:
    """每扇窗下一个木花箱：箱体 + 箱口绿植 + 一排花球。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:window-boxes")

    for op in openings:
        if op.kind != "window":
            continue
        width = op.x1 - op.x0
        if width < 0.35:
            continue
        cx = (op.x0 + op.x1) * 0.5
        half = width * 0.5 + 0.08
        z_top = op.z0 + 0.01
        z_bot = z_top - 0.26
        builder.add_box((cx - half, -0.30, z_bot), (cx + half, -0.01, z_top), BOX_SLOT)
        # 箱口压条与绿植
        builder.add_box(
            (cx - half - 0.01, -0.315, z_top - 0.05),
            (cx + half + 0.01, -0.005, z_top + 0.02),
            BOX_SLOT,
        )
        builder.add_box(
            (cx - half + 0.04, -0.27, z_top),
            (cx + half - 0.04, -0.03, z_top + 0.05),
            LEAF,
        )
        count = max(2, int(width / 0.24))
        for index in range(count):
            fx = cx - half + 0.12 + (2.0 * half - 0.24) * (index + 0.5) / count
            _blossom(
                builder,
                fx + rnd.uniform(-0.02, 0.02),
                -0.16,
                z_top + 0.04,
                rnd.uniform(0.15, 0.22),
                rnd,
            )

    return builder


def build_gable_window(
    tiles: dict[str, float],
    width: float = 0.98,
    height: float = 1.02,
    slot: str = BOX_SLOT,
    seed: int = 42,
) -> MeshBuilder:
    """山墙小窗：木框 + 十字棂 + 暖色玻璃 + 窗下花箱。

    Z=0 为窗心，Y=0 为山墙面。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:gable-window")
    hw, hh = width * 0.5, height * 0.5
    frame = 0.065

    # 玻璃：暖色，退在木框后面一点点
    builder.add_face(
        [
            (-hw + frame, -0.012, -hh + frame),
            (hw - frame, -0.012, -hh + frame),
            (hw - frame, -0.012, hh - frame),
            (-hw + frame, -0.012, hh - frame),
        ],
        FLOWER,
    )
    # 四边木框
    for x0, x1, z0, z1 in (
        (-hw, hw, -hh, -hh + frame),
        (-hw, hw, hh - frame, hh),
        (-hw, -hw + frame, -hh, hh),
        (hw - frame, hw, -hh, hh),
    ):
        builder.add_box((x0, -0.095, z0), (x1, 0.0, z1), slot)
    # 十字窗棂
    builder.add_box((-hw, -0.085, -0.028), (hw, -0.02, 0.028), slot)
    builder.add_box((-0.028, -0.085, -hh), (0.028, -0.02, hh), slot)

    # 窗下花箱（与地面窗同款，只是固定在贴面上）
    box_half = hw + 0.06
    z_top = -hh - 0.02
    builder.add_box((-box_half, -0.28, z_top - 0.24), (box_half, -0.01, z_top), slot)
    builder.add_box((-box_half + 0.04, -0.25, z_top), (box_half - 0.04, -0.03, z_top + 0.05), LEAF)
    for index in range(3):
        _blossom(
            builder,
            -box_half + 0.14 + (2.0 * box_half - 0.28) * (index + 0.5) / 3.0,
            -0.15,
            z_top + 0.04,
            0.18,
            rnd,
        )

    return builder


def build_door_dressing(
    door_cx: float,
    door_w: float,
    tiles: dict[str, float],
    seed: int = 42,
) -> MeshBuilder:
    """门口陈设：两侧石花盆 + 门洞右上角的暖光壁灯。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:door-dressing")

    for sign in (-1.0, 1.0):
        px = door_cx + sign * (door_w * 0.5 + 0.36)
        py = -0.50
        # 石盆：上口略外翻
        builder.add_box((px - 0.16, py - 0.16, 0.0), (px + 0.16, py + 0.16, 0.24), "stone")
        builder.add_box((px - 0.19, py - 0.19, 0.22), (px + 0.19, py + 0.19, 0.30), "stone")
        _blossom(builder, px, py, 0.29, 0.30, rnd)

    # 壁灯：铁艺支架 + 灯体 + 暖光面
    lx = door_cx + door_w * 0.5 + 0.26
    lz = 1.95
    builder.add_box((lx - 0.025, -0.22, lz - 0.02), (lx + 0.025, -0.02, lz + 0.02), "char")
    builder.add_box((lx - 0.08, -0.34, lz - 0.11), (lx + 0.08, -0.18, lz + 0.10), "char")
    builder.add_box((lx - 0.055, -0.355, lz - 0.075), (lx + 0.055, -0.185, lz + 0.065), FLOWER)
    builder.add_box((lx - 0.10, -0.35, lz + 0.10), (lx + 0.10, -0.17, lz + 0.145), "char")

    return builder
