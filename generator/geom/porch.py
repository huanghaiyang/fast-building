"""茅草门廊（披檐）。

局部坐标：X 以门为中心，Y=0 为外墙外表面，向 -Y 方向出挑；Z=0 为地面。
屋脊沿 Y 方向，正面是三角形茅草山墙，两侧各一根深色立柱与一道横梁。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .thatch import add_cylinder_y, add_slope, add_tube


def build_thatch_porch(
    width: float,
    depth: float,
    rise: float,
    eave_h: float,
    tiles: dict[str, float],
    thickness: float = 0.18,
    overhang: float = 0.16,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    half = width * 0.5 + overhang
    y_front = -depth - overhang
    y_back = 0.06
    z_eave = eave_h
    z_ridge = z_eave + thickness + rise

    add_slope(builder, -half, 0.0, y_front, y_back, z_eave, rise, thickness, "thatch")
    add_slope(builder, half, 0.0, y_front, y_back, z_eave, rise, thickness, "thatch")

    # 正面山墙：茅草封满，两侧加深色博风板；略微外移避免共面
    builder.add_face(
        [
            (-half, y_front - 0.008, z_eave + thickness),
            (0.0, y_front - 0.008, z_ridge),
            (half, y_front - 0.008, z_eave + thickness),
            (half, y_front - 0.008, z_eave),
            (-half, y_front - 0.008, z_eave),
        ],
        "thatch",
    )
    # 博风板：沿两坡山墙边缘的深色木条
    slope_len = (half * half + rise * rise) ** 0.5
    for sign in (-1.0, 1.0):
        nx, nz = rise * sign / slope_len, half / slope_len
        y = y_front - 0.02
        p0 = (sign * half, y, z_eave + thickness)
        p1 = (0.0, y, z_ridge)
        board = 0.12
        builder.add_face(
            [
                p0,
                p1,
                (p1[0] + nx * board, y, p1[2] + nz * board),
                (p0[0] + nx * board, y, p0[2] + nz * board),
            ],
            "trim",
        )

    # 脊梁
    builder.add_box(
        (-0.07, y_front - 0.10, z_ridge - 0.03),
        (0.07, y_back, z_ridge + 0.09),
        "trim",
    )
    # 檐口压边
    lip = thickness * 0.5
    add_cylinder_y(builder, y_front, y_back, -half, z_eave + lip, lip, "thatch")
    add_cylinder_y(builder, y_front, y_back, half, z_eave + lip, lip, "thatch")
    # 山墙滚边
    for x_eave in (-half, half):
        add_tube(
            builder,
            (x_eave, y_front - 0.01, z_eave + lip),
            (0.0, y_front - 0.01, z_ridge - lip),
            lip + 0.02,
            "thatch",
        )
    # 前檐横梁
    builder.add_box(
        (-half, y_front - 0.02, z_eave - 0.14),
        (half, y_front + 0.12, z_eave),
        "trim",
    )
    # 立柱
    post_x = half - 0.13
    post_y = y_front + 0.13
    for x in (-post_x, post_x):
        builder.add_box(
            (x - 0.10, post_y - 0.10, 0.0),
            (x + 0.10, post_y + 0.10, z_eave),
            "trim",
        )
    return builder
