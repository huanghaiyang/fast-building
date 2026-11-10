"""茅草门廊（披檐）。

局部坐标：X 以门为中心，Y=0 为外墙外表面，向 -Y 方向出挑；Z=0 为地面。
屋脊沿 Y 方向，正面是三角形茅草山墙，两侧各一根深色立柱立在石台上。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .thatch import add_cylinder_y, add_slope


def build_thatch_porch(
    width: float,
    depth: float,
    rise: float,
    eave_h: float,
    tiles: dict[str, float],
    thickness: float = 0.20,
    overhang: float = 0.16,
    platform_h: float = 0.22,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    half = width * 0.5 + overhang
    y_front = -depth - overhang
    y_back = 0.02
    z_eave = eave_h
    z_ridge = z_eave + thickness + rise

    # 石台：让门廊立柱有落脚点，同时垫高入口
    builder.add_box(
        (-half + 0.04, y_front + 0.04, 0.0),
        (half - 0.04, -0.24, platform_h),
        "stone",
    )

    add_slope(builder, -half, 0.0, y_front, y_back, z_eave, rise, thickness, "thatch")
    add_slope(builder, half, 0.0, y_front, y_back, z_eave, rise, thickness, "thatch")

    # 正面山墙：茅草封满（略微内凹，让坡面端露出草层厚度）
    builder.add_face(
        [
            (-half, y_front + 0.006, z_eave + thickness),
            (0.0, y_front + 0.006, z_ridge),
            (half, y_front + 0.006, z_eave + thickness),
            (half, y_front + 0.006, z_eave),
            (-half, y_front + 0.006, z_eave),
        ],
        "thatch",
    )

    # 博风板：沿两坡山墙边缘的深色木条
    slope_len = (half * half + rise * rise) ** 0.5
    for sign in (-1.0, 1.0):
        nx, nz = -sign * rise / slope_len, -half / slope_len
        y_a, y_b = y_front - 0.05, y_front + 0.004
        board = 0.12
        p0 = (sign * half, 0.0, z_eave)
        p1 = (0.0, 0.0, z_ridge)
        a = [
            (p0[0], y_a, p0[2]),
            (p1[0], y_a, p1[2]),
            (p1[0] + nx * board, y_a, p1[2] + nz * board),
            (p0[0] + nx * board, y_a, p0[2] + nz * board),
        ]
        b = [(x, y_b, z) for x, _, z in a]
        builder.add_face(a, "trim")
        builder.add_face([b[3], b[2], b[1], b[0]], "trim")
        builder.add_face([a[0], a[1], b[1], b[0]], "trim")
        builder.add_face([a[3], b[3], b[2], a[2]], "trim")
        builder.add_face([a[0], b[0], b[3], a[3]], "trim")
        builder.add_face([a[1], a[2], b[2], b[1]], "trim")

    # 脊梁
    builder.add_box(
        (-0.06, y_front - 0.08, z_ridge - 0.05),
        (0.06, y_back, z_ridge + 0.03),
        "trim",
    )
    # 檐口压边
    lip = thickness * 0.5
    add_cylinder_y(builder, y_front, y_back, -half, z_eave + lip, lip, "thatch")
    add_cylinder_y(builder, y_front, y_back, half, z_eave + lip, lip, "thatch")
    # 前檐封檐板
    builder.add_box(
        (-half, y_front - 0.02, z_eave - 0.12),
        (half, y_front + 0.16, z_eave),
        "trim",
    )
    # 立柱
    post_x = half - 0.13
    post_y = y_front + 0.13
    for x in (-post_x, post_x):
        builder.add_box(
            (x - 0.10, post_y - 0.10, platform_h),
            (x + 0.10, post_y + 0.10, z_eave),
            "trim",
        )
    return builder
