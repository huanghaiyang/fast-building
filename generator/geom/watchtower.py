"""石砌瞭望塔的塔顶木构：阶梯石基、悬挑挑廊、木构瞭望棚。

参考图里的塔由三段组成：宽大的阶梯石基、笔直的石砌塔身，以及塔顶一圈
外挑的木挑廊——托架从塔身斜撑出去，托起木板楼面，四周立栏杆，一角挂木梯；
挑廊当中是一间木板小屋，四角立柱顶着出檐很深的瓦顶。

局部坐标：0..width / 0..depth 与楼板一致，挑廊以自身楼面为 z=0。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder

# 与装配层共用的尺寸常量（单位：米）
HOARDING_OVERHANG = 0.55
HOARDING_FLOOR_T = 0.16
HOARDING_RAIL_H = 1.02
LOOKOUT_INSET = 0.42
LOOKOUT_WALL_H = 1.55
LOOKOUT_WALL_T = 0.14


def _sweep(
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
        builder.add_face([near[index], near[(index + 1) % 4], far[(index + 1) % 4], far[index]], slot)


def build_stepped_base(
    width: float,
    depth: float,
    top_z: float,
    tiles: dict[str, float],
    tiers: int = 3,
    total_h: float = 1.3,
    max_out: float = 1.3,
) -> MeshBuilder:
    """三级收分的石台基：越往下越宽，转角像条石砌出的塔座。"""
    builder = MeshBuilder(tiles)
    tier_h = total_h / max(1, tiers)
    for index in range(tiers):
        out = max_out * (tiers - index) / tiers
        z0 = top_z - total_h + tier_h * index
        builder.add_box((-out, -out, z0), (width + out, depth + out, z0 + tier_h), "stone")
    return builder


def build_hoarding(
    width: float,
    depth: float,
    tiles: dict[str, float],
    overhang: float = HOARDING_OVERHANG,
    rail_h: float = HOARDING_RAIL_H,
    ladder_drop: float = 3.2,
) -> MeshBuilder:
    """塔顶悬挑挑廊：斜撑托架 + 木板楼面 + 栏杆 + 挂在右侧的木梯。"""
    builder = MeshBuilder(tiles)
    ox = overhang
    floor_t = HOARDING_FLOOR_T

    # 楼面
    builder.add_box((-ox, -ox, 0.0), (width + ox, depth + ox, floor_t), "log")

    # 托架：从塔身斜撑到挑廊外沿
    brace_z = -0.95
    brace_top = -0.02
    for x in (0.18, width * 0.5, width - 0.18):
        _sweep(builder, (x, 0.02, brace_z), (x, -ox + 0.08, brace_top), (1.0, 0.0, 0.0), 0.14, 0.15, "log")
        _sweep(builder, (x, depth - 0.02, brace_z), (x, depth + ox - 0.08, brace_top), (1.0, 0.0, 0.0), 0.14, 0.15, "log")
    for y in (depth * 0.34, depth * 0.66):
        _sweep(builder, (0.02, y, brace_z), (-ox + 0.08, y, brace_top), (0.0, 1.0, 0.0), 0.14, 0.15, "log")
        _sweep(builder, (width - 0.02, y, brace_z), (width + ox - 0.08, y, brace_top), (0.0, 1.0, 0.0), 0.14, 0.15, "log")

    rail_top = floor_t + rail_h
    # 四角立柱
    for px in (-ox, width + ox - 0.13):
        for py in (-ox, depth + ox - 0.13):
            builder.add_box((px, py, floor_t), (px + 0.13, py + 0.13, rail_top), "log")

    # 上下横档
    for y0, y1 in ((-ox, -ox + 0.09), (depth + ox - 0.09, depth + ox)):
        builder.add_box((-ox, y0, rail_top - 0.08), (width + ox, y1, rail_top), "log")
        builder.add_box((-ox, y0, floor_t + 0.12), (width + ox, y1, floor_t + 0.2), "log")
    for x0, x1 in ((-ox, -ox + 0.09), (width + ox - 0.09, width + ox)):
        builder.add_box((x0, -ox, rail_top - 0.08), (x1, depth + ox, rail_top), "log")
        builder.add_box((x0, -ox, floor_t + 0.12), (x1, depth + ox, floor_t + 0.2), "log")

    # 栏板：沿四边按约 0.3 m 间距排布，右侧留出上下木梯的缺口
    ladder_y = depth * 0.5
    span_x = width + 2 * ox
    count_x = max(2, int(span_x / 0.3))
    for index in range(1, count_x):
        px = -ox + span_x * index / count_x
        for py in (-ox + 0.2, depth + ox - 0.2):
            builder.add_box((px - 0.06, py - 0.05, floor_t), (px + 0.06, py + 0.05, rail_top), "log")
    span_y = depth + 2 * ox
    count_y = max(2, int(span_y / 0.3))
    for index in range(1, count_y):
        py = -ox + span_y * index / count_y
        for px in (-ox + 0.2, width + ox - 0.2):
            if abs(px - (width + ox - 0.2)) < 1e-3 and abs(py - ladder_y) < 0.42:
                continue
            builder.add_box((px - 0.05, py - 0.06, floor_t), (px + 0.05, py + 0.06, rail_top), "log")

    # 木梯：贴在塔身右侧，从挑廊楼面往下垂
    ladder_x0 = width + 0.03
    ladder_x1 = width + 0.16
    for py in (ladder_y - 0.24, ladder_y + 0.17):
        builder.add_box((ladder_x0, py, -ladder_drop), (ladder_x1, py + 0.07, floor_t), "log")
    rungs = int(ladder_drop / 0.33)
    for index in range(1, rungs + 1):
        z = -ladder_drop + index * 0.33
        builder.add_box((ladder_x0 + 0.01, ladder_y - 0.24, z), (ladder_x1 - 0.02, ladder_y + 0.24, z + 0.055), "log")

    return builder


def _wall_with_hole(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
    hole: tuple[float, float, float, float] | None,
    slot: str,
) -> None:
    """一堵薄板墙；hole 为 (x0, x1, z0, z1) 的矩形洞口，用四块板围出来。"""
    if hole is None:
        builder.add_box((x0, y0, z0), (x1, y1, z1), slot)
        return
    hx0, hx1, hz0, hz1 = hole
    hx0 = min(max(hx0, x0 + 0.05), x1 - 0.05)
    hx1 = min(max(hx1, hx0 + 0.05), x1 - 0.05)
    builder.add_box((x0, y0, z0), (hx0, y1, z1), slot)
    builder.add_box((hx1, y0, z0), (x1, y1, z1), slot)
    builder.add_box((hx0, y0, z0), (hx1, y1, hz0), slot)
    builder.add_box((hx0, y0, hz1), (hx1, y1, z1), slot)


def build_lookout(
    width: float,
    depth: float,
    tiles: dict[str, float],
    wall_h: float = LOOKOUT_WALL_H,
    inset: float = LOOKOUT_INSET,
) -> MeshBuilder:
    """挑廊上的木板瞭望棚：四面木板墙（正面留门、两侧开小窗）+ 四角立柱 + 压顶枋。"""
    builder = MeshBuilder(tiles)
    x0, x1 = inset, width - inset
    y0, y1 = inset, depth - inset
    wall_t = LOOKOUT_WALL_T
    post = 0.15
    door_w = 0.72
    door_h = wall_h - 0.2
    cx = width * 0.5

    # 正面：中间留门洞
    _wall_with_hole(
        builder, x0, x1, y0, y0 + wall_t, 0.0, wall_h,
        (cx - door_w * 0.5, cx + door_w * 0.5, 0.0, door_h), "log",
    )
    # 背面：实墙
    _wall_with_hole(builder, x0, x1, y1 - wall_t, y1, 0.0, wall_h, None, "log")
    # 两侧：各开一个窄窗（薄墙沿 Y 方向断开，需单独按 Y 切分）
    wy0, wy1 = depth * 0.5 - 0.2, depth * 0.5 + 0.2
    for wx0, wx1 in ((x0, x0 + wall_t), (x1 - wall_t, x1)):
        builder.add_box((wx0, y0, 0.0), (wx1, wy0, wall_h), "log")
        builder.add_box((wx0, wy1, 0.0), (wx1, y1, wall_h), "log")
        builder.add_box((wx0, wy0, 0.0), (wx1, wy1, 0.62), "log")
        builder.add_box((wx0, wy0, 1.06), (wx1, wy1, wall_h), "log")

    # 四角立柱与压顶枋
    for px in (x0, x1 - post):
        for py in (y0, y1 - post):
            builder.add_box((px, py, 0.0), (px + post, py + post, wall_h + 0.12), "log")
    beam = 0.1
    for py in (y0, y1 - beam):
        builder.add_box((x0, py, wall_h), (x1, py + beam, wall_h + 0.12), "log")
    for px in (x0, x1 - beam):
        builder.add_box((px, y0, wall_h), (px + beam, y1, wall_h + 0.12), "log")

    return builder
