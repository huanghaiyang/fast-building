"""商铺橱窗与货架陈列。

书店和杂货铺的立面重点是「一整面被货品填满的大窗」：木框、玻璃、层板，
以及层板上密排的书脊或陶罐。这里把这一整组做成一个构件，嵌在墙板已经挖出的
大窗洞里，向墙外浅浅凸出 0.26 m，读起来就是一间装着玻璃的陈列柜。

关键几何约定：墙体洞口在 Y ∈ [0, thickness] 之间是空的，所以陈列柜的
「背板 → 货品 → 玻璃 → 外框」沿 -Y 方向层层向外排开，货品不会被墙里的
玻璃面片挡住；装配阶段对橱窗开间关掉墙板自带的玻璃（glazed=False）。

局部坐标与墙板一致：X 沿墙、Y=0 为墙外饰面（-Y 朝外）、Z 自墙脚起算；
``opening`` 用墙板同一个 ``Opening`` 描述，因此不会和洞口错位。
"""

from __future__ import annotations

import random

from ..meshkit import MeshBuilder
from .props import CLAY, GLOW, PAPER, WOOD, add_pot
from .wall_panel import Opening

GLASS = "shop_glass"
IRON = "iron"

DEPTH = 0.27
FRAME = 0.075
# 陈列区（相对墙外饰面的 Y 区间）
BACK_Y = 0.008
ITEM_Y0, ITEM_Y1 = -0.185, -0.045
GLASS_Y = -0.215
FRAME_Y = -0.255


def _book_run(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    z_base: float,
    z_top: float,
    rnd: random.Random,
    slot_cycle: tuple[str, ...],
) -> None:
    """在层板上排一行竖立的书脊，厚薄高矮都带随机。"""
    cursor = x0
    index = 0
    depth0, depth1 = ITEM_Y0 + 0.015, ITEM_Y1 - 0.01
    while cursor < x1 - 0.03:
        thickness = rnd.uniform(0.024, 0.058)
        if cursor + thickness > x1:
            break
        height = rnd.uniform(0.60, 0.95) * (z_top - z_base)
        slot = slot_cycle[index % len(slot_cycle)]
        builder.add_box((cursor, depth0, z_base), (cursor + thickness, depth1, z_base + height), slot)
        # 书脊上的烫金压条，近看才有的细节
        if thickness > 0.034 and rnd.random() < 0.5:
            band_z = z_base + height * rnd.uniform(0.55, 0.8)
            builder.add_box(
                (cursor + 0.004, depth0 - 0.006, band_z),
                (cursor + thickness - 0.004, depth0 + 0.002, band_z + 0.016),
                PAPER,
            )
        cursor += thickness + rnd.uniform(0.002, 0.01)
        index += 1


def _shelf_books(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    rows: int,
    rnd: random.Random,
) -> None:
    """多层书架：每层一块层板 + 一排书；顶层再横放一摞。"""
    slot_cycle = (PAPER, CLAY, "door", "leaf", GLOW, "cloth")
    gap = (z1 - z0) / rows
    for row in range(rows):
        z_floor = z0 + gap * row
        builder.add_box(
            (x0 - 0.02, ITEM_Y0 - 0.02, z_floor),
            (x1 + 0.02, ITEM_Y1 + 0.02, z_floor + 0.042),
            WOOD,
        )
        _book_run(builder, x0 + 0.02, x1 - 0.02, z_floor + 0.042, z_floor + gap - 0.05, rnd, slot_cycle)
    # 最上层横放一摞书
    top_z = z0 + gap * rows
    for index in range(3):
        builder.add_box(
            (x0 + 0.07 + index * 0.02, ITEM_Y0 + 0.02, top_z + 0.04 + index * 0.045),
            (x0 + 0.32 + index * 0.02, ITEM_Y1, top_z + 0.075 + index * 0.045),
            slot_cycle[index % len(slot_cycle)],
        )


def _shelf_goods(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    rows: int,
    rnd: random.Random,
) -> None:
    """多层货架：陶罐、麻袋、藤篮混排。"""
    gap = (z1 - z0) / rows
    for row in range(rows):
        z_floor = z0 + gap * row
        builder.add_box(
            (x0 - 0.02, ITEM_Y0 - 0.02, z_floor),
            (x1 + 0.02, ITEM_Y1 + 0.02, z_floor + 0.045),
            WOOD,
        )
        cursor = x0 + 0.07
        while cursor < x1 - 0.12:
            radius = rnd.uniform(0.06, 0.09)
            height = min(gap - 0.10, rnd.uniform(0.16, 0.28))
            add_pot(
                builder,
                cursor + radius,
                (ITEM_Y0 + ITEM_Y1) * 0.5,
                z_floor + 0.045,
                radius=radius,
                height=height,
            )
            cursor += radius * 2.0 + rnd.uniform(0.02, 0.08)
    # 顶层再压两袋货
    top_z = z0 + gap * rows
    for index in range(2):
        bx = x0 + 0.10 + index * 0.36
        builder.add_box((bx, ITEM_Y0, top_z + 0.04), (bx + 0.28, ITEM_Y1, top_z + 0.24), "cloth")


def build_shop_window(
    opening: Opening,
    thickness: float,
    tiles: dict[str, float],
    kind: str = "books",
    seed: int = 42,
    glazed: bool = True,
    rows: int = 3,
) -> MeshBuilder:
    """橱窗/货架组件，局部坐标同墙板（Y=0 为外饰面，-Y 朝外）。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:shopfront:{kind}")
    x0, x1 = opening.x0, opening.x1
    z0, z1 = opening.z0, opening.z1
    if x1 - x0 < 0.5 or z1 - z0 < 0.5:
        return builder

    # 内衬：暖光（书店里点着灯）或木板（杂货铺的背板）
    lining_slot = GLOW if kind == "books" else "door"
    builder.add_face(
        [
            (x0 + 0.01, BACK_Y, z0 + 0.01),
            (x1 - 0.01, BACK_Y, z0 + 0.01),
            (x1 - 0.01, BACK_Y, z1 - 0.01),
            (x0 + 0.01, BACK_Y, z1 - 0.01),
        ],
        lining_slot,
    )

    # 四边框：竖梃 + 上下横档，外缘略凸出窗洞
    builder.add_box((x0 - 0.02, FRAME_Y, z1 - FRAME), (x1 + 0.02, 0.03, z1), WOOD)
    builder.add_box((x0 - 0.02, FRAME_Y - 0.03, z0 - 0.08), (x1 + 0.02, 0.04, z0 + 0.01), WOOD)
    builder.add_box((x0 - 0.02, FRAME_Y, z0), (x0 + FRAME, 0.03, z1), WOOD)
    builder.add_box((x1 - FRAME, FRAME_Y, z0), (x1 + 0.02, 0.03, z1), WOOD)

    inner_x0, inner_x1 = x0 + FRAME, x1 - FRAME
    inner_z0, inner_z1 = z0 + 0.03, z1 - FRAME

    if kind == "books":
        _shelf_books(builder, inner_x0, inner_x1, inner_z0, inner_z1, rows, rnd)
    else:
        _shelf_goods(builder, inner_x0, inner_x1, inner_z0, inner_z1, rows, rnd)

    if glazed:
        # 玻璃与窗棂：一竖两横，把大窗分成六格
        builder.add_face(
            [
                (inner_x0 + 0.01, GLASS_Y, inner_z0),
                (inner_x1 - 0.01, GLASS_Y, inner_z0),
                (inner_x1 - 0.01, GLASS_Y, inner_z1),
                (inner_x0 + 0.01, GLASS_Y, inner_z1),
            ],
            GLASS,
        )
        mid_x = (inner_x0 + inner_x1) * 0.5
        builder.add_box(
            (mid_x - 0.032, GLASS_Y - 0.03, inner_z0), (mid_x + 0.032, GLASS_Y + 0.03, inner_z1), WOOD
        )
        for frac in (0.34, 0.67):
            mz = inner_z0 + (inner_z1 - inner_z0) * frac
            builder.add_box(
                (inner_x0, GLASS_Y - 0.03, mz - 0.026), (inner_x1, GLASS_Y + 0.03, mz + 0.026), WOOD
            )

    # 窗台板与底下两个小托木
    builder.add_box((x0 - 0.10, FRAME_Y - 0.06, z0 - 0.17), (x1 + 0.10, 0.03, z0 - 0.07), WOOD)
    for frac in (0.22, 0.78):
        bx = x0 + (x1 - x0) * frac
        builder.add_box((bx - 0.045, FRAME_Y + 0.02, z0 - 0.36), (bx + 0.045, 0.0, z0 - 0.15), WOOD)

    # 顶上的小挑檐，替橱窗挡雨
    builder.add_box((x0 - 0.12, FRAME_Y - 0.14, z1), (x1 + 0.12, 0.05, z1 + 0.10), "roof")
    for frac in (0.16, 0.84):
        bx = x0 + (x1 - x0) * frac
        builder.add_box((bx - 0.035, FRAME_Y - 0.02, z1 - 0.22), (bx + 0.035, 0.0, z1), WOOD)
    return builder
