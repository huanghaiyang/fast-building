"""屋顶生成：平屋顶、双坡屋顶与破损双坡屋顶。

双坡屋顶使用三角棱柱（三棱柱）构造：两个斜面 + 两个山墙三角 + 底面，
是封闭流形，不需要布尔运算，也不会出现面片翻转。

破损模式（ruin > 0）把两个坡面切成网格板，随机抽掉若干块形成破洞，
并在屋面下补出外露椽条，读起来就是失修的废墟屋顶。
"""

from __future__ import annotations

import math
import random

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
    ruin: float = 0.0,
    seed: int = 0,
    gable_slot: str = "facade",
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

    if ruin > 0.0:
        for direction in (1.0, -1.0):
            _ruined_slope(
                builder,
                x_right if direction > 0 else x_left,
                cx,
                z_top,
                rise,
                y0,
                y1,
                thickness,
                direction,
                ruin,
                random.Random(f"{seed}:{direction}"),
            )
        # 前后山墙三角：底边落到墙顶，封住檐口与屋面之间的一圈空隙
        builder.add_face([(x_left, y0, z), (x_right, y0, z), (cx, y0, z_top + rise)], gable_slot)
        builder.add_face([(x_left, y1, z), (cx, y1, z_top + rise), (x_right, y1, z)], gable_slot)
        return builder

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
    # 前后山墙：底边落到墙顶，封住檐口与屋面之间的一圈空隙
    builder.add_face([(x_left, y0, z), (x_right, y0, z), (cx, y0, z_top + rise)], gable_slot)
    builder.add_face([(x_left, y1, z), (cx, y1, z_top + rise), (x_right, y1, z)], gable_slot)
    # 底面
    builder.add_face([a, d, e, b], "trim")
    return builder


# --------------------------------------------------------------------------- 破损坡面
def _surface(x_eave: float, cx: float, z_top: float, rise: float, y: float, v: float):
    return (x_eave + (cx - x_eave) * v, y, z_top + rise * v)


def _slab(
    builder: MeshBuilder,
    corners: list[tuple[float, float, float]],
    inward: tuple[float, float],
    thickness: float,
    slot: str,
    exposed: tuple[bool, bool, bool, bool] = (True, True, True, True),
) -> None:
    """按坡面四边形生成一块带厚度的屋面板（上下两面 + 侧面）。

    ``exposed`` 标记四条边是否需要补侧壁：相邻屋面板共用一条边时，
    两侧都会生成同一条侧壁，形成朝向相反的重合面，导出时会被判为无效网格。
    """
    ix, iz = inward
    # 两个坡面的角点顺序相反，直接按顺序建面会让其中一侧法线朝内，先统一绕序
    ax, ay, az = corners[0]
    bx, by, bz = corners[1]
    qx, qy, qz = corners[2]
    nx = (by - ay) * (qz - az) - (bz - az) * (qy - ay)
    ny = (bz - az) * (qx - ax) - (bx - ax) * (qz - az)
    nz = (bx - ax) * (qy - ay) - (by - ay) * (qx - ax)
    flipped = nx * ix + ny * 0.0 + nz * iz > 0.0
    if flipped:
        corners = list(reversed(corners))
        # 角点倒序后，边 0/2 互换，边 1 与 3 各自反向，仍保持同一条边
        exposed = (exposed[2], exposed[1], exposed[0], exposed[3])
    outer = corners
    inner = [(x + ix * thickness, y, z + iz * thickness) for x, y, z in outer]
    builder.add_face(outer, slot)
    builder.add_face(list(reversed(inner)), slot)
    for index in range(4):
        if not exposed[index]:
            continue
        a = outer[index]
        b = outer[(index + 1) % 4]
        a2 = inner[index]
        b2 = inner[(index + 1) % 4]
        builder.add_face([a, b, b2, a2], slot)


def _beam(
    builder: MeshBuilder,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    side: tuple[float, float, float],
    up: tuple[float, float, float],
    width: float,
    height: float,
    slot: str,
) -> None:
    """沿两点之间扫掠一根矩形截面的梁（椽条）。"""
    def corners(point, sign_a, sign_b):
        return (
            point[0] + side[0] * width * sign_a + up[0] * height * sign_b,
            point[1] + side[1] * width * sign_a + up[1] * height * sign_b,
            point[2] + side[2] * width * sign_a + up[2] * height * sign_b,
        )

    quad = [corners(p0, 0.5, 0.5), corners(p0, -0.5, 0.5), corners(p0, -0.5, -0.5), corners(p0, 0.5, -0.5)]
    far = [corners(p1, 0.5, 0.5), corners(p1, -0.5, 0.5), corners(p1, -0.5, -0.5), corners(p1, 0.5, -0.5)]
    builder.add_face(quad, slot)
    builder.add_face(list(reversed(far)), slot)
    for index in range(4):
        builder.add_face(
            [quad[index], quad[(index + 1) % 4], far[(index + 1) % 4], far[index]],
            slot,
        )


def _ruined_slope(
    builder: MeshBuilder,
    x_eave: float,
    cx: float,
    z_top: float,
    rise: float,
    y0: float,
    y1: float,
    thickness: float,
    direction: float,
    ruin: float,
    rnd: random.Random,
) -> None:
    """一侧坡面：网格屋面板 + 随机破洞 + 屋面下的外露椽条。"""
    half = abs(cx - x_eave)
    length = math.hypot(half, rise)
    # 外法线（指向上方并向外）
    nx, nz = rise / length * direction, half / length
    inward = (-nx * thickness, -nz * thickness)
    inward_unit = (-nx, -nz)

    rows = [0.0, 0.36, 0.64, 0.86, 1.0]
    columns = max(3, int(round((y1 - y0) / 1.05)))
    edges = [y0]
    for index in range(1, columns):
        edges.append(y0 + (y1 - y0) * index / columns + rnd.uniform(-0.16, 0.16))
    edges.append(y1)

    # 破洞：只抽中段行，保留檐口与屋脊轮廓
    middle = [(col, row) for row in (1, 2, 3) for col in range(columns)]
    holes = set()
    count = min(len(middle) // 2, max(3, int(round(ruin * 12))))
    for _ in range(count):
        cell = rnd.choice(middle)
        holes.add(cell)
        if rnd.random() < 0.55:
            neighbour = (min(columns - 1, cell[0] + 1), cell[1])
            if neighbour in middle:
                holes.add(neighbour)

    for col in range(columns):
        u0, u1 = edges[col], edges[col + 1]
        for row in range(len(rows) - 1):
            if (col, row) in holes:
                continue
            v0, v1 = rows[row], rows[row + 1]
            corners = [
                _surface(x_eave, cx, z_top, rise, u0, v0),
                _surface(x_eave, cx, z_top, rise, u1, v0),
                _surface(x_eave, cx, z_top, rise, u1, v1),
                _surface(x_eave, cx, z_top, rise, u0, v1),
            ]
            _slab(builder, corners, inward, thickness, "roof")

    # 椽条：沿坡向从檐口到屋脊，贴在屋面下
    side = (0.0, 1.0, 0.0)
    up = (nx, 0.0, nz)
    offset = thickness + 0.075
    for index in range(columns + 1):
        u = edges[index]
        p0 = _surface(x_eave, cx, z_top, rise, u, 0.0)
        p1 = _surface(x_eave, cx, z_top, rise, u, 1.0)
        p0 = (p0[0] + inward_unit[0] * offset, p0[1], p0[2] + inward_unit[1] * offset)
        p1 = (p1[0] + inward_unit[0] * offset, p1[1], p1[2] + inward_unit[1] * offset)
        _beam(builder, p0, p1, side, up, 0.09, 0.14, "trim")
