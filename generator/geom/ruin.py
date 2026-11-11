"""坍塌石屋废墟。

参考图可以拆成四件事：

1. 四面灰岩石墙只剩半截，墙顶是参差的锯齿，墙角保留较高；
2. 地面铺满碎石与断板，墙脚的石堆更厚；
3. 两根烧焦的长梁斜插在墙内，末端劈裂、探出墙头；
4. 一段烧毁的木构架横躺在瓦砾上。

坐标约定：正面朝 -Y，平面占 x∈[0,width]、y∈[0,depth]，z=0 为地面。
墙体在局部坐标里生成（x 沿墙长、y 为厚度、z 为高度），
碎石与焦木直接按世界坐标生成，避免再套一层变换。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder


# --------------------------------------------------------------------------- 基础体块
def _basis(direction: tuple[float, float, float]):
    """给一根任意方向的杆件求正交基：方向、侧向、上向。"""
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    axis = (dx / length, dy / length, dz / length)
    up = (0.0, 0.0, 1.0)
    if abs(axis[2]) > 0.92:
        up = (1.0, 0.0, 0.0)
    sx = axis[1] * up[2] - axis[2] * up[1]
    sy = axis[2] * up[0] - axis[0] * up[2]
    sz = axis[0] * up[1] - axis[1] * up[0]
    sl = math.sqrt(sx * sx + sy * sy + sz * sz) or 1.0
    side = (sx / sl, sy / sl, sz / sl)
    ux = side[1] * axis[2] - side[2] * axis[1]
    uy = side[2] * axis[0] - side[0] * axis[2]
    uz = side[0] * axis[1] - side[1] * axis[0]
    return axis, side, (ux, uy, uz)


def _box_between(
    builder: MeshBuilder,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    width: float,
    height: float,
    slot: str = "log",
    end_scale: float = 1.0,
) -> None:
    """两点之间的方杆；end_scale < 1 时末端收细，读成劈裂/焦断的木头。"""
    _, side, up = _basis((p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]))
    hw, hh = width * 0.5, height * 0.5

    def ring(point, scale):
        return [
            (point[0] - side[0] * hw * scale - up[0] * hh * scale,
             point[1] - side[1] * hw * scale - up[1] * hh * scale,
             point[2] - side[2] * hw * scale - up[2] * hh * scale),
            (point[0] + side[0] * hw * scale - up[0] * hh * scale,
             point[1] + side[1] * hw * scale - up[1] * hh * scale,
             point[2] + side[2] * hw * scale - up[2] * hh * scale),
            (point[0] + side[0] * hw * scale + up[0] * hh * scale,
             point[1] + side[1] * hw * scale + up[1] * hh * scale,
             point[2] + side[2] * hw * scale + up[2] * hh * scale),
            (point[0] - side[0] * hw * scale + up[0] * hh * scale,
             point[1] - side[1] * hw * scale + up[1] * hh * scale,
             point[2] - side[2] * hw * scale + up[2] * hh * scale),
        ]

    start = ring(p0, 1.0)
    end = ring(p1, end_scale)
    for index in range(4):
        builder.add_face(
            [start[index], start[(index + 1) % 4], end[(index + 1) % 4], end[index]],
            slot,
        )
    builder.add_face(list(reversed(start)), slot)
    builder.add_face(end, slot)


def _rock(
    builder: MeshBuilder,
    center: tuple[float, float, float],
    size: float,
    rnd: random.Random,
    slot: str = "stone",
) -> None:
    """低面数碎石：上下两圈随机半径的棱环 + 顶点，读起来像带棱角的毛石。"""
    cx, cy, cz = center
    sides = rnd.randint(5, 7)
    phase = rnd.uniform(0.0, math.tau)
    lower: list[tuple[float, float, float]] = []
    upper: list[tuple[float, float, float]] = []
    for index in range(sides):
        angle = phase + math.tau * index / sides
        low_r = size * rnd.uniform(0.72, 0.98)
        up_r = size * rnd.uniform(0.55, 0.86)
        lower.append(
            (
                cx + math.cos(angle) * low_r,
                cy + math.sin(angle) * low_r,
                cz - size * rnd.uniform(0.3, 0.45),
            )
        )
        upper.append(
            (
                cx + math.cos(angle) * up_r,
                cy + math.sin(angle) * up_r,
                cz + size * rnd.uniform(0.18, 0.38),
            )
        )
    top = (
        cx + size * rnd.uniform(-0.2, 0.2),
        cy + size * rnd.uniform(-0.2, 0.2),
        cz + size * rnd.uniform(0.42, 0.62),
    )
    bottom = (cx, cy, cz - size * 0.46)
    for index in range(sides):
        nxt = (index + 1) % sides
        builder.add_face([lower[index], lower[nxt], upper[nxt], upper[index]], slot)
        builder.add_face([upper[index], upper[nxt], top], slot)
        builder.add_face([lower[nxt], lower[index], bottom], slot)


# --------------------------------------------------------------------------- 残墙
def _slice_bounds(length: float, extra: tuple[float, ...], rnd: random.Random) -> list[float]:
    count = max(3, int(round(length / 0.46)))
    bounds = [length * index / count for index in range(count + 1)]
    for value in extra:
        if 0.06 < value < length - 0.06:
            bounds.append(value)
    return sorted({round(value, 5) for value in bounds})


def _broken_wall(
    length: float,
    height: float,
    thickness: float,
    tiles: dict[str, float],
    rnd: random.Random,
    holes: list[tuple[float, float, float, float]],
    slot: str = "stone",
    height_scale: float = 1.0,
    notch: float = 0.0,
) -> MeshBuilder:
    """带参差断口的石墙；holes 为（x0, x1, z0, z1）的洞口。

    height_scale 控制整面墙的残高，notch > 0 时在墙中段再塌出一个 V 形缺口。
    """
    builder = MeshBuilder(tiles)
    extra: list[float] = []
    for hole in holes:
        extra.extend((hole[0], hole[1]))
    bounds = _slice_bounds(length, tuple(extra), rnd)

    count = len(bounds) - 1
    heights: list[float] = []
    level = rnd.uniform(0.8, 0.98)
    for index in range(count):
        edge = min(index, count - 1 - index)
        # 靠墙角的两三片保留较多，中段塌得更狠
        cap = 0.52 + 0.45 * min(1.0, edge / 2.0)
        target = cap * rnd.uniform(0.82, 1.04)
        level = level * 0.45 + target * 0.55
        heights.append(min(0.99, max(0.24, level)))
    heights = [value * height_scale for value in heights]

    if notch > 0.0:
        center = rnd.uniform(0.26, 0.66)
        width = rnd.uniform(0.16, 0.28)
        for index in range(count):
            mid = (index + 0.5) / count
            distance = abs(mid - center) / width
            if distance < 1.0:
                heights[index] *= 0.3 + 0.7 * distance

    # 落地洞口两侧的墙头抬到门顶以上，门洞上方的墙体才不会悬空
    for hole in holes:
        if hole[2] > 0.01:
            continue
        need = min(1.0, (hole[3] + 0.4) / height)
        for index in range(count):
            if bounds[index] < hole[1] + 0.6 and bounds[index + 1] > hole[0] - 0.6:
                heights[index] = max(heights[index], need)

    for index in range(count):
        x0, x1 = bounds[index], bounds[index + 1]
        top = height * heights[index]
        spans = [(0.0, top)]
        for hole in holes:
            if hole[1] <= x0 + 1e-4 or hole[0] >= x1 - 1e-4:
                continue
            cut0, cut1 = hole[2], min(hole[3], top)
            if cut1 <= cut0 + 0.02:
                continue
            remain: list[tuple[float, float]] = []
            for z0, z1 in spans:
                if cut1 <= z0 or cut0 >= z1:
                    remain.append((z0, z1))
                    continue
                if cut0 > z0 + 0.02:
                    remain.append((z0, cut0))
                if z1 > cut1 + 0.02:
                    remain.append((cut1, z1))
            spans = remain
        for z0, z1 in spans:
            if z1 - z0 < 0.06:
                continue
            # 相邻竖条之间留 1.5 mm 重叠，避免共面重合导致导出器报 mesh invalid
            pad = 0.0015
            builder.add_box((x0 - pad, 0.0, z0 - pad), (x1 + pad, thickness, z1 + pad), slot)

        # 墙顶散落的碎石：打断整齐的台阶轮廓
        if top > height * 0.4 and rnd.random() < 0.8:
            for _ in range(rnd.randint(0, 2)):
                width = min(x1 - x0, rnd.uniform(0.12, 0.3))
                if width < 0.1:
                    continue
                tx = rnd.uniform(x0, x1 - width)
                builder.add_box(
                    (tx, rnd.uniform(-0.035, 0.005), top - 0.05),
                    (tx + width, thickness + rnd.uniform(-0.005, 0.035), top + rnd.uniform(0.05, 0.2)),
                    slot,
                )
    return builder


def _door_surround(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    z1: float,
    thickness: float,
    slot: str,
) -> None:
    """门洞的毛石框：两侧门垛 + 压顶，略微凸出墙面。"""
    jamb, proud = 0.22, 0.05
    builder.add_box((x0 - jamb, -proud, 0.0), (x0, thickness + proud, z1 + 0.08), slot)
    builder.add_box((x1, -proud, 0.0), (x1 + jamb, thickness + proud, z1 + 0.08), slot)
    builder.add_box((x0 - jamb, -proud, z1), (x1 + jamb, thickness + proud, z1 + 0.2), slot)


# --------------------------------------------------------------------------- 瓦砾与焦木
def build_rubble(
    width: float,
    depth: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
    scale: float = 1.0,
) -> MeshBuilder:
    """室内外的碎石、断板与塌落的石堆。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:rubble")

    # 碎石：室内堆成斜坡，墙脚更厚；室外是一圈散落的碎石带
    inside = int(width * depth * 9)
    outside = int((width + depth) * 8)
    for _ in range(inside):
        x = rnd.uniform(0.12, width - 0.12)
        y = rnd.uniform(0.12, depth - 0.12)
        big = rnd.random() < 0.18
        size = (rnd.uniform(0.28, 0.58) if big else rnd.uniform(0.08, 0.22)) * scale
        # 靠墙的石堆更高：塌落的墙石先堆在墙脚
        edge = max(0.0, min(x, width - x, y, depth - y))
        mound = 0.18 + 0.72 * math.exp(-edge / 1.0)
        _rock(builder, (x, y, mound + size * 0.3), size, rnd, "stone")

    # 塌落的墙体大块：比碎石更能读成「墙倒了」
    for _ in range(8):
        cx = rnd.uniform(0.5, width - 0.5)
        cy = rnd.uniform(0.5, depth - 0.5)
        angle = rnd.uniform(0.0, math.tau)
        half = rnd.uniform(0.3, 0.65)
        z = rnd.uniform(0.12, 0.5)
        _box_between(
            builder,
            (cx - math.cos(angle) * half, cy - math.sin(angle) * half, z),
            (cx + math.cos(angle) * half, cy + math.sin(angle) * half, z + rnd.uniform(-0.12, 0.18)),
            rnd.uniform(0.3, 0.46),
            rnd.uniform(0.22, 0.34),
            "stone",
        )

    for _ in range(outside):
        wall = rnd.randrange(4)
        spread = rnd.uniform(0.1, 2.3)
        along = rnd.uniform(-0.6, 1.6)
        if wall == 0:
            x, y = rnd.uniform(-0.6, width + 0.6), -spread
        elif wall == 1:
            x, y = rnd.uniform(-0.6, width + 0.6), depth + spread
        elif wall == 2:
            x, y = -spread, rnd.uniform(-0.6, depth + 0.6)
        else:
            x, y = width + spread, rnd.uniform(-0.6, depth + 0.6)
        size = rnd.uniform(0.06, 0.2) * scale * (1.0 - min(spread / 3.2, 0.55))
        _rock(builder, (x + along * 0.3, y + along * 0.3, size * 0.35), size, rnd, "stone")

    # 断板：贴地或压在石堆上的细长木片
    for _ in range(22):
        cx = rnd.uniform(-0.6, width + 0.6)
        cy = rnd.uniform(-0.6, depth + 0.6)
        inside_pt = 0.0 <= cx <= width and 0.0 <= cy <= depth
        base = rnd.uniform(0.12, 0.42) if inside_pt else 0.04
        angle = rnd.uniform(0.0, math.tau)
        length = rnd.uniform(0.6, 2.0)
        dx, dy = math.cos(angle) * length * 0.5, math.sin(angle) * length * 0.5
        _box_between(
            builder,
            (cx - dx, cy - dy, base),
            (cx + dx, cy + dy, base + rnd.uniform(0.0, 0.16)),
            rnd.uniform(0.16, 0.26),
            0.035,
            "log",
        )

    return builder


def build_charred_timber(
    width: float,
    depth: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
    slot: str = "door",
) -> MeshBuilder:
    """烧焦的长梁与塌落的木构架；slot 用深色门板材质，读起来像炭化的木头。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:timber")

    # 两根交叉的长梁：斜插进内墙，梁头探出墙头并分叉
    beams = [
        (
            (width * rnd.uniform(0.18, 0.3), depth * rnd.uniform(0.72, 0.9), 0.22),
            (width * rnd.uniform(0.58, 0.72), depth * rnd.uniform(0.08, 0.24), height * rnd.uniform(1.15, 1.4)),
        ),
        (
            (width * rnd.uniform(0.68, 0.82), depth * rnd.uniform(0.14, 0.3), 0.18),
            (width * rnd.uniform(0.26, 0.38), depth * rnd.uniform(0.78, 0.92), height * rnd.uniform(1.05, 1.28)),
        ),
    ]
    for p0, p1 in beams:
        _box_between(builder, p0, p1, 0.26, 0.3, slot, end_scale=0.52)
        # 劈裂的梁头：从 0.78 处长出第二根短枝
        fork = (
            p0[0] + (p1[0] - p0[0]) * 0.78,
            p0[1] + (p1[1] - p0[1]) * 0.78,
            p0[2] + (p1[2] - p0[2]) * 0.78,
        )
        side = rnd.uniform(-0.5, 0.5)
        _box_between(
            builder,
            fork,
            (
                p1[0] + (p1[1] - p0[1]) * side * 0.4,
                p1[1] - (p1[0] - p0[0]) * side * 0.4,
                p1[2] + rnd.uniform(0.15, 0.45),
            ),
            0.13,
            0.15,
            slot,
            end_scale=0.35,
        )

    # 两根短梁斜靠在墙头
    for _ in range(2):
        p0 = (rnd.uniform(0.8, width - 0.8), rnd.uniform(0.8, depth - 0.8), 0.1)
        p1 = (p0[0] + rnd.uniform(-1.2, 1.2), p0[1] + rnd.uniform(-1.2, 1.2), height * rnd.uniform(0.5, 0.8))
        _box_between(builder, p0, p1, 0.18, 0.2, slot, end_scale=0.7)

    # 塌落的木构架：两根柱子 + 上下横档 + 斜撑，歪在瓦砾上
    fx = width * rnd.uniform(0.46, 0.62)
    fy = depth * rnd.uniform(0.42, 0.6)
    lean = 0.18
    post_a0 = (fx, fy, 0.05)
    post_a1 = (fx + lean, fy + 0.05, rnd.uniform(1.0, 1.3))
    post_b0 = (fx + 1.05, fy + 0.28, 0.05)
    post_b1 = (fx + 1.05 + lean, fy + 0.3, rnd.uniform(0.62, 0.86))
    _box_between(builder, post_a0, post_a1, 0.14, 0.14, slot, end_scale=0.85)
    _box_between(builder, post_b0, post_b1, 0.14, 0.14, slot, end_scale=0.8)
    _box_between(
        builder,
        (post_a1[0], post_a1[1], post_a1[2] - 0.06),
        (post_b1[0], post_b1[1], post_b1[2] + 0.12),
        0.12,
        0.12,
        slot,
        end_scale=0.9,
    )
    _box_between(
        builder,
        (fx + 0.06, fy + 0.04, 0.5),
        (fx + 1.0, fy + 0.24, 0.52),
        0.1,
        0.1,
        slot,
        end_scale=0.9,
    )
    _box_between(
        builder,
        (fx + 0.1, fy + 0.04, 0.12),
        (fx + 0.55, fy + 0.16, 0.95),
        0.09,
        0.09,
        slot,
        end_scale=0.6,
    )
    return builder


# --------------------------------------------------------------------------- 斜靠与倒伏木板
def build_leaning_planks(
    width: float,
    depth: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
    door: tuple[float, float] | None = None,
    slot: str = "log",
) -> MeshBuilder:
    """墙边斜靠的木板与地上的倒伏断板。

    斜靠板一端落地、一端搭在墙面上，避开门洞；倒伏板贴近地面，
    少数压在墙脚的碎石堆上。坐标与建筑一致（正立面在 y=0）。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:planks")

    door_lo, door_hi = (-9.0, -9.0)
    if door is not None:
        door_cx, door_w = door
        door_lo = door_cx - door_w * 0.5 - 0.45
        door_hi = door_cx + door_w * 0.5 + 0.45

    def free_spot(lo: float, hi: float) -> float:
        """在 lo~hi 之间避开门口挑一个位置。"""
        for _ in range(12):
            spot = rnd.uniform(lo, hi)
            if spot < door_lo or spot > door_hi:
                return spot
        return lo

    # 正立面外侧斜靠的木板：下端离墙 0.5 m 左右，上端搭在墙面上
    for _ in range(3):
        x = free_spot(0.5, max(0.6, width - 0.5))
        reach = height * rnd.uniform(0.5, 0.8)
        _box_between(
            builder,
            (x, -rnd.uniform(0.45, 0.7), 0.02),
            (x + rnd.uniform(-0.18, 0.18), 0.02, reach),
            rnd.uniform(0.24, 0.34),
            0.045,
            slot,
            end_scale=rnd.uniform(0.8, 1.0),
        )

    # 两侧墙外斜靠的木板
    for side in (-1.0, 1.0):
        if rnd.random() < 0.35:
            continue
        y = rnd.uniform(0.8, max(0.9, depth - 0.8))
        reach = height * rnd.uniform(0.42, 0.66)
        wall_x = -0.02 if side < 0 else width + 0.02
        ground_x = wall_x + side * rnd.uniform(0.4, 0.62)
        _box_between(
            builder,
            (ground_x, y, 0.02),
            (wall_x, y + rnd.uniform(-0.25, 0.25), reach),
            rnd.uniform(0.22, 0.3),
            0.04,
            slot,
        )

    # 地上倒伏的断板：室外两块、室内三块
    for index in range(5):
        outside = index >= 3
        if outside:
            cx = rnd.uniform(-0.5, width + 0.5)
            cy = rnd.uniform(-1.1, -0.15) if rnd.random() < 0.6 else rnd.uniform(depth + 0.15, depth + 1.1)
            z = 0.03
        else:
            cx = rnd.uniform(0.4, max(0.6, width - 0.4))
            cy = rnd.uniform(0.4, max(0.6, depth - 0.4))
            z = rnd.uniform(0.05, 0.35)
        angle = rnd.uniform(0.0, math.tau)
        length = rnd.uniform(1.0, 2.2)
        dx = math.cos(angle) * length * 0.5
        dy = math.sin(angle) * length * 0.5
        _box_between(
            builder,
            (cx - dx, cy - dy, z),
            (cx + dx, cy + dy, z + rnd.uniform(-0.03, 0.1)),
            rnd.uniform(0.18, 0.3),
            0.04,
            slot,
        )

    return builder


# --------------------------------------------------------------------------- 组合
def build_collapsed_ruin(
    width: float,
    depth: float,
    wall_height: float,
    thickness: float,
    tiles: dict[str, float],
    seed: int = 42,
    door: tuple[float, float] | None = None,
    door_height: float = 2.1,
) -> dict[str, tuple[MeshBuilder, tuple[float, float, float], float]]:
    """返回 {名称: (网格, 位置, 绕 Z 旋转)}，与装配层 create_object 的调用方式一致。"""
    rnd = random.Random(f"{seed}:walls")

    door_hole: list[tuple[float, float, float, float]] = []
    if door is not None:
        door_cx, door_w = door
        x0 = max(0.4, door_cx - door_w * 0.5)
        x1 = min(width - 0.4, door_cx + door_w * 0.5)
        door_hole.append((x0, x1, 0.0, min(door_height, wall_height - 0.5)))

    front = _broken_wall(
        width, wall_height, thickness, tiles, rnd, door_hole, height_scale=0.94, notch=0.35
    )
    if door_hole:
        _door_surround(front, door_hole[0][0], door_hole[0][1], door_hole[0][3], thickness, "stone")

    back_holes = []
    if width > 4.4:
        wx = width * rnd.uniform(0.48, 0.68)
        back_holes.append((wx, wx + 0.62, 1.35, 2.1))
    back = _broken_wall(
        width, wall_height, thickness, tiles, rnd, back_holes, height_scale=0.8, notch=0.5
    )

    side_length = depth
    side_holes = []
    if depth > 4.2:
        sx = depth * rnd.uniform(0.18, 0.32)
        side_holes.append((sx, sx + 0.66, 0.0, 2.05))
    left = _broken_wall(
        side_length, wall_height, thickness, tiles, rnd, side_holes, height_scale=0.92
    )
    right = _broken_wall(
        side_length, wall_height, thickness, tiles, rnd,
        [(depth * 0.62, depth * 0.62 + 0.6, 1.5, 2.15)],
        height_scale=0.74,
        notch=0.75,
    )

    rubble = build_rubble(width, depth, wall_height, tiles, seed)
    timber = build_charred_timber(width, depth, wall_height, tiles, seed)

    return {
        "ruin_wall_front": (front, (0.0, 0.0, 0.0), 0.0),
        "ruin_wall_back": (back, (width, depth, 0.0), math.pi),
        "ruin_wall_left": (left, (0.0, depth, 0.0), -math.pi / 2),
        "ruin_wall_right": (right, (width, 0.0, 0.0), math.pi / 2),
        "ruin_rubble": (rubble, (0.0, 0.0, 0.0), 0.0),
        "ruin_timber": (timber, (0.0, 0.0, 0.0), 0.0),
    }
