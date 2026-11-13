"""水磨坊的水轮与磨坊水渠。

参考图的水磨坊靠三件东西读出来：一面巨大的木制水轮、轮下泛着水光的水池与石砌
岸线、以及从墙里伸出来往轮上送水的木水槽。这三件都做成独立构件，由装配阶段按
样式开关挂到立面上（默认挂在正面右侧）。

局部坐标：
- ``build_water_wheel``：原点在轮心，轮平面为 XZ，轮轴沿 Y（-Y 为墙外方向）；
- ``build_mill_pit``：X 以轮心为 0、Y 从墙面 0 向墙外为负、Z 自地面起算。
  轮坑、水面、石砌岸线、送水木槽与支架都在这一套坐标里，方便整组摆放。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .props import WOOD, _box_frame, prism_y, ring_y

LOG = "log"
STONE = "stone"
WATER = "water"
IRON = "iron"

# 水轮相对轮径的默认比例
RIM_T = 0.13
PADDLE_RATIO = 0.20


def build_water_wheel(
    tiles: dict[str, float],
    radius: float = 1.95,
    width: float = 0.62,
    paddles: int = 16,
    spokes: int = 8,
) -> MeshBuilder:
    """木制水轮：双轮缘 + 内圈 + 辐条 + 叶片 + 轮毂 + 轮轴。"""
    builder = MeshBuilder(tiles)
    half_w = width * 0.5
    rim_out = radius
    rim_in = radius - RIM_T
    inner_ring = radius * 0.52
    hub_r = max(0.16, radius * 0.10)

    # 双轮缘（内外两圈木环，略作分层以便读出厚度）
    for y0, y1 in ((-half_w, -half_w + 0.10), (half_w - 0.10, half_w)):
        ring_y(builder, 0.0, 0.0, y0, y1, rim_out, rim_in, sides=28, slot=LOG)
        ring_y(
            builder,
            0.0,
            0.0,
            y0 + 0.01,
            y1 - 0.01,
            inner_ring + 0.07,
            inner_ring - 0.07,
            sides=24,
            slot=LOG,
        )

    # 辐条：轮毂到轮缘，两侧各一排
    for index in range(spokes):
        angle = 2.0 * math.pi * index / spokes
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        radial = (cos_a, 0.0, sin_a)
        tangential = (-sin_a, 0.0, cos_a)
        length = rim_in - hub_r
        center_r = hub_r + length * 0.5
        for y in (-half_w + 0.12, half_w - 0.12):
            _box_frame(
                builder,
                (radial[0] * center_r, y, radial[2] * center_r),
                (radial, tangential, (0.0, 1.0, 0.0)),
                (length * 0.5, 0.055, 0.05),
                LOG,
            )

    # 叶片：沿切线方向铺的宽木板，跨在两道轮缘之间
    paddle_half = radius * PADDLE_RATIO
    for index in range(paddles):
        angle = 2.0 * math.pi * (index + 0.25) / paddles
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        radial = (cos_a, 0.0, sin_a)
        tangential = (-sin_a, 0.0, cos_a)
        radius_at = rim_in - PADDLE_RATIO * radius * 0.5
        _box_frame(
            builder,
            (radial[0] * radius_at, 0.0, radial[2] * radius_at),
            (tangential, radial, (0.0, 1.0, 0.0)),
            (paddle_half, 0.030, width * 0.46),
            WOOD,
        )

    # 轮毂与轮轴
    prism_y(builder, 0.0, 0.0, -half_w - 0.06, half_w + 0.06, hub_r, sides=12, slot=LOG)
    prism_y(builder, 0.0, 0.0, -half_w - 0.34, 0.55, hub_r * 0.52, sides=10, slot=LOG)
    # 轮轴两端的铁箍
    for y in (-half_w - 0.30, -half_w - 0.10, half_w + 0.02):
        ring_y(builder, 0.0, 0.0, y, y + 0.055, hub_r * 0.62, hub_r * 0.50, sides=10, slot=IRON)
    return builder


def build_mill_pit(
    tiles: dict[str, float],
    radius: float = 1.95,
    width: float = 0.62,
    sluice_side: float = -1.0,
    pit_depth: float = 0.55,
    water_level: float = 0.10,
    axle_ratio: float = 0.84,
) -> MeshBuilder:
    """轮坑、水面、石岸、送水木槽与支架（整组放在墙脚外侧）。"""
    builder = MeshBuilder(tiles)
    out_front = -(width * 0.5 + 1.35)
    out_back = -0.02
    left = -(radius * 0.78 + 0.52)
    right = radius * 0.78 + 0.52
    curb_h = 0.15
    curb_t = 0.30

    # 轮坑底面与四面石岸（前、后、左、右），底部沉到地下
    builder.add_box((left, out_front, -pit_depth), (right, out_back, -pit_depth + 0.10), STONE)
    for x0, x1, y0, y1 in (
        (left, right, out_front, out_front + curb_t),
        (left, right, out_back - curb_t, out_back),
        (left, left + curb_t, out_front, out_back),
        (right - curb_t, right, out_front, out_back),
    ):
        builder.add_box((x0, y0, -pit_depth), (x1, y1, curb_h), STONE)
        # 岸顶压一道条石
        builder.add_box((x0 - 0.02, y0 - 0.02, curb_h), (x1 + 0.02, y1 + 0.02, curb_h + 0.06), STONE)

    # 水面：一整片半透明薄板，略低于石岸
    builder.add_face(
        [
            (left + curb_t, out_front + curb_t, water_level),
            (right - curb_t, out_front + curb_t, water_level),
            (right - curb_t, out_back - curb_t, water_level),
            (left + curb_t, out_back - curb_t, water_level),
        ],
        WATER,
    )
    # 水面下的暗色底（避免从水面直接看穿到地面）
    builder.add_box(
        (left + curb_t, out_front + curb_t, -pit_depth + 0.10),
        (right - curb_t, out_back - curb_t, water_level - 0.02),
        "char",
    )

    # 轮轴两侧的石墩 + 铁轴承：水轮是架在石墩上转的，不是浮在墙面上
    axle_z = radius * max(0.55, axle_ratio)
    for y in (-width * 0.5 - 0.20, width * 0.5 + 0.20):
        builder.add_box((-0.22, y - 0.11, 0.0), (0.40, y + 0.11, axle_z - 0.16), STONE)
        builder.add_box((-0.26, y - 0.14, axle_z - 0.20), (0.44, y + 0.14, axle_z - 0.01), STONE)
        builder.add_box((-0.20, y - 0.09, axle_z - 0.12), (0.38, y + 0.09, axle_z + 0.02), IRON)
    builder.add_box((-0.20, -width * 0.5 - 0.24, axle_z - 0.05), (0.38, width * 0.5 + 0.24, axle_z + 0.06), LOG)

    # 送水木槽：从墙面高处伸出，槽尾悬在轮顶上游侧，槽口有水帘落向轮缘
    side = -1.0 if sluice_side <= 0 else 1.0
    wheel_top = radius * (max(0.55, axle_ratio) + 1.0)
    trough_z = wheel_top + 0.20
    start = (side * radius * 0.10, out_back, trough_z + 0.14)
    end = (side * radius * 0.86, -(width * 0.5 + 0.78), trough_z - 0.26)
    segments = 5
    for index in range(segments):
        f0 = index / segments
        f1 = (index + 1) / segments
        ax = start[0] + (end[0] - start[0]) * f0
        az = start[2] + (end[2] - start[2]) * f0
        bx = start[0] + (end[0] - start[0]) * f1
        bz = start[2] + (end[2] - start[2]) * f1
        ay = start[1] + (end[1] - start[1]) * f0
        by = start[1] + (end[1] - start[1]) * f1
        _box_frame(
            builder,
            ((ax + bx) * 0.5, (ay + by) * 0.5, (az + bz) * 0.5 - 0.07),
            (
                ((bx - ax), (by - ay), (bz - az)),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
            (0.34, 0.15, 0.10),
            WOOD,
        )
    # 槽内水带
    _box_frame(
        builder,
        ((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5, (start[2] + end[2]) * 0.5 + 0.01),
        (
            ((end[0] - start[0]), (end[1] - start[1]), (end[2] - start[2])),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        (0.34, 0.09, 0.006),
        WATER,
    )

    # 槽口垂下的水帘：从槽尾落到轮缘上，水磨的「正在干活」就靠这一片水
    builder.add_face(
        [
            (end[0] - 0.28, end[1] - 0.01, end[2] - 0.10),
            (end[0] + 0.28, end[1] - 0.01, end[2] - 0.10),
            (end[0] + 0.24, end[1] - 0.16, wheel_top - 0.55),
            (end[0] - 0.24, end[1] - 0.16, wheel_top - 0.55),
        ],
        WATER,
    )

    # 支架：一根斜撑从墙面顶住水槽尾端，另加一根立柱落在石岸上
    brace_y = end[1] + 0.12
    builder.add_box(
        (end[0] - 0.07, out_back - 0.14, trough_z - 1.55),
        (end[0] + 0.07, out_back, trough_z - 1.40),
        LOG,
    )
    _box_frame(
        builder,
        (end[0], (brace_y + out_back) * 0.5, trough_z - 1.02),
        ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
        (abs(brace_y - out_back) * 0.55, 0.06, 0.07),
        LOG,
    )
    return builder
