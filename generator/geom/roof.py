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
    gable_ruin: float = 0.0,
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
    rnd = random.Random(f"{seed}:gable")

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
        _gable_face(builder, x_left, x_right, cx, z, z_top, rise, y0, gable_slot, rnd, gable_ruin)
        _gable_face(
            builder, x_left, x_right, cx, z, z_top, rise, y1, gable_slot, rnd, gable_ruin, flip=True
        )
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
    _gable_face(builder, x_left, x_right, cx, z, z_top, rise, y0, gable_slot, rnd, gable_ruin)
    _gable_face(
        builder, x_left, x_right, cx, z, z_top, rise, y1, gable_slot, rnd, gable_ruin, flip=True
    )
    # 底面
    builder.add_face([a, d, e, b], "trim")
    return builder


def _gable_face(
    builder: MeshBuilder,
    x_left: float,
    x_right: float,
    cx: float,
    z: float,
    z_eave: float,
    rise: float,
    y: float,
    slot: str,
    rnd: random.Random,
    ruin: float = 0.0,
    flip: bool = False,
) -> None:
    """一片山墙；ruin > 0 时顶边按种子崩缺，退化成参差的断墙。

    flip 用于后侧山墙：两面朝向相反，否则后山墙的法线会指向室内。
    """
    if ruin <= 0.0:
        points = [(x_left, y, z), (x_right, y, z), (cx, y, z_eave + rise)]
        builder.add_face(list(reversed(points)) if flip else points, slot)
        return

    half = (x_right - x_left) * 0.5
    count = max(6, int(round((x_right - x_left) / 0.42)))
    for index in range(count):
        x0 = x_left + (x_right - x_left) * index / count
        x1 = x_left + (x_right - x_left) * (index + 1) / count
        mid = (x0 + x1) * 0.5
        profile = z_eave + rise * max(0.0, 1.0 - abs(mid - cx) / half)
        roll = rnd.random()
        if roll < 0.34:
            top = profile
        elif roll < 0.60:
            top = profile - rnd.uniform(0.1, 0.35)
        elif roll < 0.85:
            top = profile - rnd.uniform(0.4, 0.8)
        else:
            top = profile - rnd.uniform(0.9, 1.6)
        # 塌透的片段：只留墙脚一点的残石
        if ruin > 0.4 and rnd.random() < 0.09 * ruin * 2.0:
            top = z + rnd.uniform(0.1, 0.3)
        # 靠近檐口的两端保留多一点，山墙才立得住
        if min(mid - x_left, x_right - mid) < 0.8:
            top = max(top, profile - 0.12)
        top = max(top, z + 0.24)
        strip = [(x0, y, z), (x1, y, z), (x1, y, top), (x0, y, top)]
        builder.add_face(list(reversed(strip)) if flip else strip, slot)
        # 崩口上方零星的残石
        if top > z + 0.6 and rnd.random() < 0.45:
            width = min(x1 - x0, rnd.uniform(0.1, 0.22))
            tx = rnd.uniform(x0, max(x0, x1 - width))
            chip = [
                (tx, y, top - 0.04),
                (tx + width, y, top - 0.04),
                (tx + width, y, top + rnd.uniform(0.06, 0.2)),
                (tx, y, top + rnd.uniform(0.06, 0.2)),
            ]
            builder.add_face(list(reversed(chip)) if flip else chip, slot)


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


# --------------------------------------------------------------------------- 露明梁架
def build_open_roof_frame(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    tiles: dict[str, float],
    seed: int = 42,
    gable_slot: str = "facade",
    timber_slot: str = "log",
    gable_ruin: float = 0.6,
    gable_drop: float = 0.12,
) -> MeshBuilder:
    """只剩梁架的双坡顶：破损山墙 + 脊梁、檐檩与椽条，屋面石板全部塌落。

    山墙整体下压 gable_drop，正好挡住侧墙残顶的断口，避免山墙悬空。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:open-roof")
    half = (width + 2 * overhang) * 0.5
    cx = width * 0.5
    y0 = -overhang
    y1 = depth + overhang
    rise = math.tan(math.radians(pitch_deg)) * half
    x_left = cx - half
    x_right = cx + half
    z_top = z + 0.2

    _gable_face(
        builder, x_left, x_right, cx, z - gable_drop, z_top, rise, y0 - 0.03, gable_slot,
        random.Random(f"{seed}:gable-front"), gable_ruin,
    )
    _gable_face(
        builder, x_left, x_right, cx, z - gable_drop, z_top, rise, y1 + 0.03, gable_slot,
        random.Random(f"{seed}:gable-back"), gable_ruin, flip=True,
    )

    # 脊梁与两侧檐檩：沿进深方向的通长木梁
    _beam(
        builder,
        (cx, y0 - 0.22, z_top + rise - 0.18),
        (cx, y1 + 0.22, z_top + rise - 0.18),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        0.20,
        0.30,
        timber_slot,
    )
    for x in (x_left + 0.16, x_right - 0.16):
        _beam(
            builder,
            (x, y0, z_top - 0.02),
            (x, y1, z_top - 0.02),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            0.16,
            0.20,
            timber_slot,
        )

    # 椽条：每坡沿进深密排，零星缺失读成塌落
    columns = max(3, int(round((y1 - y0) / 0.72)))
    for index in range(columns + 1):
        y = y0 + (y1 - y0) * index / columns
        missing = rnd.random() < 0.14
        for direction in (-1.0, 1.0):
            if missing:
                continue
            x_eave = x_right - 0.06 if direction > 0 else x_left + 0.06
            ax, az = cx - x_eave, rise
            length = math.hypot(ax, az) or 1.0
            # 截面朝上的法线，保证木梁宽面贴着坡面
            up = (-az / length, 0.0, ax / length)
            if up[2] < 0.0:
                up = (-up[0], 0.0, -up[2])
            _beam(
                builder,
                (x_eave, y, z_top + 0.04),
                (cx, y, z_top + rise - 0.02),
                (0.0, 1.0, 0.0),
                up,
                0.09,
                0.16,
                timber_slot,
            )

    # 残存的系梁：水平横跨两坡
    for ratio in (0.34, 0.66):
        for spot in (0.26, 0.62):
            y = y0 + (y1 - y0) * spot
            zz = z_top + rise * ratio
            offset = half * ratio
            _beam(
                builder,
                (cx - offset, y, zz),
                (cx + offset, y, zz),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
                0.10,
                0.14,
                timber_slot,
            )
    return builder
