"""半木构客栈的环绕木廊。

二层向外挑出一圈木质外廊：楼面前、左、右三面连通并挑出墙面，外侧一圈
栏杆（上下压条 + 密排栏杆条），转角立木柱，栏杆下方用斜撑把外挑楼面
拉回墙身。全部由轴对齐盒体与矩形截面扫掠构成，不做布尔运算。

局部坐标：0..width / 0..depth 与楼板一致，正面朝 -Y；z=0 为楼板底面。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder

GALLERY_DEPTH = 0.90
GALLERY_FLOOR_T = 0.16
GALLERY_RAIL_H = 1.02
POST = 0.14
RAIL_T = 0.10
RAIL_BAND = 0.10
BALUSTER = 0.05
BALUSTER_GAP = 0.30
BRACE = 0.12


def sweep_box(
    builder: MeshBuilder,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    side: tuple[float, float, float],
    width: float,
    thick: float,
    slot: str,
) -> None:
    """沿 p0→p1 扫出一根矩形截面的斜撑；side 为截面宽度方向。"""
    d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    up = (
        side[1] * d[2] - side[2] * d[1],
        side[2] * d[0] - side[0] * d[2],
        side[0] * d[1] - side[1] * d[0],
    )
    length = math.sqrt(up[0] ** 2 + up[1] ** 2 + up[2] ** 2)
    if length < 1e-5:
        return
    up = (up[0] / length * thick * 0.5, up[1] / length * thick * 0.5, up[2] / length * thick * 0.5)
    half = (side[0] * width * 0.5, side[1] * width * 0.5, side[2] * width * 0.5)

    def corner(point, a: float, b: float):
        return (
            point[0] + half[0] * a + up[0] * b,
            point[1] + half[1] * a + up[1] * b,
            point[2] + half[2] * a + up[2] * b,
        )

    near = [corner(p0, 1, 1), corner(p0, -1, 1), corner(p0, -1, -1), corner(p0, 1, -1)]
    far = [corner(p1, 1, 1), corner(p1, -1, 1), corner(p1, -1, -1), corner(p1, 1, -1)]
    builder.add_face(near, slot)
    builder.add_face(list(reversed(far)), slot)
    for index in range(4):
        builder.add_face(
            [near[index], near[(index + 1) % 4], far[(index + 1) % 4], far[index]], slot
        )


def _rail_x(
    builder: MeshBuilder, x0: float, x1: float, y: float, z: float, rail_h: float
) -> None:
    """沿 X 方向的栏杆段（y 为栏杆外皮）。"""
    z_rail = z + rail_h
    builder.add_box((x0, y, z), (x1, y + RAIL_T, z + RAIL_BAND), "trim")
    builder.add_box((x0, y, z_rail - RAIL_BAND), (x1, y + RAIL_T, z_rail), "trim")
    span = x1 - x0
    count = max(2, int(round(span / BALUSTER_GAP)))
    for index in range(1, count):
        u = x0 + span * index / count
        builder.add_box(
            (u - BALUSTER * 0.5, y + 0.02, z + RAIL_BAND),
            (u + BALUSTER * 0.5, y + RAIL_T - 0.02, z_rail - RAIL_BAND),
            "trim",
        )


def _rail_y(
    builder: MeshBuilder, y0: float, y1: float, x: float, z: float, rail_h: float
) -> None:
    """沿 Y 方向的栏杆段（x 为栏杆外皮）。"""
    z_rail = z + rail_h
    builder.add_box((x, y0, z), (x + RAIL_T, y1, z + RAIL_BAND), "trim")
    builder.add_box((x, y0, z_rail - RAIL_BAND), (x + RAIL_T, y1, z_rail), "trim")
    span = y1 - y0
    count = max(2, int(round(span / BALUSTER_GAP)))
    for index in range(1, count):
        u = y0 + span * index / count
        builder.add_box(
            (x + 0.02, u - BALUSTER * 0.5, z + RAIL_BAND),
            (x + RAIL_T - 0.02, u + BALUSTER * 0.5, z_rail - RAIL_BAND),
            "trim",
        )


def build_gallery(
    width: float,
    depth: float,
    z: float,
    tiles: dict[str, float],
    depth_out: float = GALLERY_DEPTH,
    rail_h: float = GALLERY_RAIL_H,
) -> MeshBuilder:
    """三面环绕木廊：木楼面 + 栏杆 + 转角木柱 + 底部斜撑。"""
    builder = MeshBuilder(tiles)
    o = depth_out
    z_floor = z + GALLERY_FLOOR_T

    # 楼面：正面通长，左右两条补到后墙角
    builder.add_box((-o, -o, z), (width + o, 0.0, z_floor), "trim")
    builder.add_box((-o, 0.0, z), (0.0, depth, z_floor), "trim")
    builder.add_box((width, 0.0, z), (width + o, depth, z_floor), "trim")

    # 栏杆：外皮对齐楼面外缘
    _rail_x(builder, -o + POST, width + o - POST, -o, z_floor, rail_h)
    _rail_y(builder, -o + POST, depth - POST * 0.5, -o, z_floor, rail_h)
    _rail_y(builder, -o + POST, depth - POST * 0.5, width + o - RAIL_T, z_floor, rail_h)

    # 转角柱与跨中柱：从楼面顶到压条上方
    post_h = rail_h + 0.06
    for px, py in (
        (-o, -o),
        (width + o - POST, -o),
        (-o, depth - POST),
        (width + o - POST, depth - POST),
    ):
        builder.add_box(
            (px, py, z_floor - 0.02), (px + POST, py + POST, z_floor + post_h), "trim"
        )
    span = width + 2 * o - 2 * POST
    count = max(2, int(round(span / 2.4)))
    for index in range(1, count):
        px = -o + POST + span * index / count
        builder.add_box(
            (px - POST * 0.5, -o, z_floor - 0.02),
            (px + POST * 0.5, -o + POST, z_floor + post_h),
            "trim",
        )

    # 底部斜撑：从墙身斜撑到楼面外沿
    drop = 0.62
    if width > 1.4:
        braces = max(2, int(round(width / 2.2)))
        for index in range(braces + 1):
            bx = 0.25 + (width - 0.5) * index / braces
            sweep_box(
                builder,
                (bx, -0.02, z - drop),
                (bx, -o + 0.08, z - 0.02),
                (1.0, 0.0, 0.0),
                BRACE,
                BRACE,
                "trim",
            )
    side_braces = max(1, int(round(depth / 2.4)))
    for index in range(side_braces + 1):
        by = 0.25 + (depth - 0.5) * index / side_braces
        sweep_box(
            builder,
            (-0.02, by, z - drop),
            (-o + 0.08, by, z - 0.02),
            (0.0, 1.0, 0.0),
            BRACE,
            BRACE,
            "trim",
        )
        sweep_box(
            builder,
            (width + 0.02, by, z - drop),
            (width + o - 0.08, by, z - 0.02),
            (0.0, 1.0, 0.0),
            BRACE,
            BRACE,
            "trim",
        )

    return builder
