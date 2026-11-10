"""厚茅草双坡屋顶。

与瓦屋顶的三角棱柱不同，茅草屋顶强调「厚」与「大出檐」：
- 坡面是有竖向厚度的实心棱柱，檐口加半圆压边，形成圆润的草边；
- 山墙三角面用茅草封满（真实茅草屋常见做法）；
- 屋脊压一根深色原木脊梁，两端略微出挑。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder


def add_slope(
    builder: MeshBuilder,
    x_eave: float,
    x_ridge: float,
    y0: float,
    y1: float,
    z_eave: float,
    rise: float,
    thickness: float,
    slot: str = "thatch",
) -> None:
    """添加一个带竖向厚度的坡面棱柱（檐口在 x_eave，屋脊在 x_ridge）。"""
    z_eave_top = z_eave + thickness
    z_ridge_top = z_eave + thickness + rise
    z_ridge_bot = z_eave + rise

    eb0 = (x_eave, y0, z_eave)
    eb1 = (x_eave, y1, z_eave)
    et0 = (x_eave, y0, z_eave_top)
    et1 = (x_eave, y1, z_eave_top)
    rt0 = (x_ridge, y0, z_ridge_top)
    rt1 = (x_ridge, y1, z_ridge_top)
    rb0 = (x_ridge, y0, z_ridge_bot)
    rb1 = (x_ridge, y1, z_ridge_bot)

    builder.add_face([et0, rt0, rt1, et1], slot)  # 上表面
    builder.add_face([eb0, eb1, rb1, rb0], slot)  # 下表面
    builder.add_face([eb0, eb1, et1, et0], slot)  # 檐口立面
    builder.add_face([eb0, et0, rt0, rb0], slot)  # 山墙端封边
    builder.add_face([eb1, rb1, rt1, et1], slot)
    # 脊部不封口：两坡在此共线，补面会与对侧坡面重合，形成重复面


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(a):
    length = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def add_tube(
    builder: MeshBuilder,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    slot: str = "thatch",
    segments: int = 8,
) -> None:
    """任意方向的圆管，用于茅草山墙的厚重滚边。"""
    axis = _normalize((end[0] - start[0], end[1] - start[1], end[2] - start[2]))
    ref = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _normalize(_cross(axis, ref))
    v = _cross(axis, u)
    tile = builder.tiles.get(slot, 2.0)
    length = math.dist(start, end)
    arc = 2.0 * math.pi * radius

    offsets = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        cr, sr = math.cos(angle) * radius, math.sin(angle) * radius
        offsets.append((u[0] * cr + v[0] * sr, u[1] * cr + v[1] * sr, u[2] * cr + v[2] * sr))

    for i in range(segments):
        o0 = offsets[i]
        o1 = offsets[(i + 1) % segments]
        u0 = arc * i / segments / tile
        u1 = arc * (i + 1) / segments / tile
        builder.add_face(
            [
                (start[0] + o0[0], start[1] + o0[1], start[2] + o0[2]),
                (end[0] + o0[0], end[1] + o0[1], end[2] + o0[2]),
                (end[0] + o1[0], end[1] + o1[1], end[2] + o1[2]),
                (start[0] + o1[0], start[1] + o1[1], start[2] + o1[2]),
            ],
            slot,
            uvs=[(0.0, u0), (length / tile, u0), (length / tile, u1), (0.0, u1)],
        )
    for point in (start, end):
        builder.add_face(
            [(point[0] + o[0], point[1] + o[1], point[2] + o[2]) for o in offsets], slot
        )


def add_cylinder_y(
    builder: MeshBuilder,
    y0: float,
    y1: float,
    x_center: float,
    z_center: float,
    radius: float,
    slot: str = "thatch",
    segments: int = 8,
) -> None:
    """沿 Y 的半圆压边（檐口、门廊檐口用），UV 的木纹/草纹沿 Y 展开。"""
    if y1 - y0 < 0.02:
        return
    tile = builder.tiles.get(slot, 2.0)
    arc = 2.0 * math.pi * radius
    ring = [
        (
            radius * math.cos(2.0 * math.pi * i / segments),
            radius * math.sin(2.0 * math.pi * i / segments),
        )
        for i in range(segments)
    ]
    for i in range(segments):
        x0, z0 = ring[i]
        x1, z1 = ring[(i + 1) % segments]
        u0 = arc * i / segments / tile
        u1 = arc * (i + 1) / segments / tile
        builder.add_face(
            [
                (x_center + x0, y0, z_center + z0),
                (x_center + x0, y1, z_center + z0),
                (x_center + x1, y1, z_center + z1),
                (x_center + x1, y0, z_center + z1),
            ],
            slot,
            uvs=[(y0 / tile, u0), (y1 / tile, u0), (y1 / tile, u1), (y0 / tile, u1)],
        )
    for y in (y0, y1):
        builder.add_face([(x_center + x, y, z_center + z) for x, z in ring], slot)


def build_thatch_roof(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
    gable_slot: str = "thatch",
) -> MeshBuilder:
    """厚茅草双坡屋顶；局部坐标与 build_gable_roof 一致。"""
    builder = MeshBuilder(tiles)
    half = width * 0.5 + overhang
    cx = width * 0.5
    x_left = cx - half
    x_right = cx + half
    y0 = -overhang
    y1 = depth + overhang
    rise = math.tan(math.radians(pitch_deg)) * half

    add_slope(builder, x_left, cx, y0, y1, z, rise, thickness, "thatch")
    add_slope(builder, x_right, cx, y0, y1, z, rise, thickness, "thatch")

    # 山墙三角（从檐口下缘一直填到屋脊），让屋面从两端看是整块茅草
    z_top = z + thickness
    z_ridge = z_top + rise
    # 略微外移，避免与坡面端封边共面产生 z-fighting
    inset = 0.008
    for y in (y0 - inset, y1 + inset):
        builder.add_face(
            [
                (x_left, y, z_top),
                (cx, y, z_ridge),
                (x_right, y, z_top),
                (x_right, y, z),
                (x_left, y, z),
            ],
            gable_slot,
        )

    # 檐口半圆压边
    lip = thickness * 0.5
    add_cylinder_y(builder, y0, y1, x_left, z + lip, lip, "thatch")
    add_cylinder_y(builder, y0, y1, x_right, z + lip, lip, "thatch")

    # 山墙檐口滚边：沿两坡的山墙边缘各压一根粗草卷，形成厚重的金色草边
    roll = thickness * 0.5 + 0.02
    for y in (y0 - 0.01, y1 + 0.01):
        add_tube(builder, (x_left, y, z + lip), (cx, y, z_ridge - lip), roll, "thatch")
        add_tube(builder, (x_right, y, z + lip), (cx, y, z_ridge - lip), roll, "thatch")

    # 屋脊原木脊梁，两端出挑
    builder.add_box(
        (cx - 0.09, y0 - 0.14, z_ridge - 0.04),
        (cx + 0.09, y1 + 0.14, z_ridge + 0.11),
        "trim",
    )
    return builder
