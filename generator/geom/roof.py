"""屋顶生成：平屋顶与双坡屋顶。

双坡屋顶使用三角棱柱（三棱柱）构造：两个斜面 + 两个山墙三角 + 底面，
是封闭流形，不需要布尔运算，也不会出现面片翻转。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder


def build_flat_roof(
    width: float,
    depth: float,
    z: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    builder.add_box(
        (-overhang, -overhang, z),
        (width + overhang, depth + overhang, z + thickness),
        "roof",
    )
    return builder


def build_gable_roof(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    half = (width + 2 * overhang) * 0.5
    cx = width * 0.5
    y0 = -overhang
    y1 = depth + overhang
    rise = math.tan(math.radians(pitch_deg)) * half
    x_left = cx - half
    x_right = cx + half
    z_top = z + thickness

    # 六个顶点：左右檐口 + 屋脊，前后各一组
    a = (x_left, y0, z_top)
    b = (x_right, y0, z_top)
    c = (cx, y0, z_top + rise)
    d = (x_left, y1, z_top)
    e = (x_right, y1, z_top)
    f = (cx, y1, z_top + rise)

    # 两个坡面
    builder.add_face([a, c, f, d], "roof")
    builder.add_face([b, e, f, c], "roof")
    # 前后山墙
    builder.add_face([a, b, c], "facade")
    builder.add_face([d, f, e], "facade")
    # 底面
    builder.add_face([a, d, e, b], "trim")
    return builder
