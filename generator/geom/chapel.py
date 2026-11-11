"""废墟哥特教堂的专属构件：西端方形钟塔、纵向残破坡顶与破损山墙。

参考图可以拆成四件事：

1. 西端一座方形石钟塔，塔身比中殿高一倍多，上部一圈成对尖拱百叶窗，
   塔顶残缺、四角小尖塔折断；
2. 中殿屋脊沿长轴，屋面大部分塌掉，只剩檐口与屋脊附近的零星石板；
3. 露出的红棕色椽条沿坡向密排，檐口探出椽尾，屋脊下方压着脊梁与檩条；
4. 山墙顶边随屋面收尖但参差崩缺，墙脚散落碎石。

坐标约定：
- 钟塔为局部坐标，x 沿塔宽、y 沿塔深（0 为正面）、z 自地面起算；
- 坡顶与山墙直接使用世界坐标，装配层只负责平移到建筑原点。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder, face_normal
from .arch import arch_strips
from .roof import _beam
from .wall_panel import Opening, build_wall_panel

TOWER_WALL_T = 0.42


# --------------------------------------------------------------------------- 通用工具
def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _merge(builder: MeshBuilder, part: MeshBuilder) -> None:
    """把另一块网格并进当前构建器，并按坐标去重顶点。"""
    index = [builder._vert(point) for point in part.verts]  # noqa: SLF001
    for face, slot, uvs in zip(part.faces, part.face_slots, part.face_uvs):
        builder.faces.append([index[i] for i in face])
        builder.face_slots.append(slot)
        builder.face_uvs.append(uvs)


def _patch(
    builder: MeshBuilder,
    corners: list[tuple[float, float, float]],
    normal: tuple[float, float, float],
    thickness: float,
    slot: str,
    exposed: tuple[bool, bool, bool, bool] = (True, True, True, True),
) -> None:
    """带厚度的一块屋面石板；normal 为外法线，exposed 标记哪几条边要补侧壁。"""
    facing = face_normal(corners)
    if facing[0] * normal[0] + facing[1] * normal[1] + facing[2] * normal[2] < 0.0:
        corners = list(reversed(corners))
        exposed = (exposed[2], exposed[1], exposed[0], exposed[3])
    nx, ny, nz = normal
    inner = [
        (x - nx * thickness, y - ny * thickness, z - nz * thickness)
        for x, y, z in corners
    ]
    builder.add_face(corners, slot)
    builder.add_face(list(reversed(inner)), slot)
    for index in range(4):
        if not exposed[index]:
            continue
        a = corners[index]
        b = corners[(index + 1) % 4]
        a2 = inner[index]
        b2 = inner[(index + 1) % 4]
        builder.add_face([a, b, b2, a2], slot)


# --------------------------------------------------------------------------- 方形钟塔
def _tower_face(
    span: float,
    height: float,
    stage: float,
    belfry: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    """一面的塔身：下段一扇细长枪眼，上段一对尖拱百叶窗，洞口通透。"""
    cx = span * 0.5
    lancet_w = min(0.50, span * 0.16)
    slit_w = min(0.26, span * 0.085)
    pair_w = min(0.66, span * 0.19)
    gap = pair_w * 0.58
    left = cx - (pair_w * 2 + gap) * 0.5

    openings = [
        Opening(cx - lancet_w * 0.5, cx + lancet_w * 0.5, stage * 0.52, stage * 0.78, "window"),
        # 塔脚附近一条窄缝，近看才分得清
        Opening(cx - slit_w * 0.5, cx + slit_w * 0.5, stage * 0.14, stage * 0.27, "window"),
        Opening(left, left + pair_w, stage + 0.82, belfry - 0.58, "window"),
        Opening(left + pair_w + gap, left + pair_w * 2 + gap, stage + 0.82, belfry - 0.58, "window"),
    ]
    strips: list[Opening] = []
    for op in openings:
        strips.extend(arch_strips(op))
    return build_wall_panel(
        span, height, TOWER_WALL_T, strips, tiles, glazing=False, edge_slot="stone"
    )


def _corner_pinnacle(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    tip: float,
    slot: str,
) -> None:
    """断掉的角部小尖塔：三级收分的方墩，顶端高度随机。"""
    for half, height in ((0.32, 0.26), (0.23, 0.30)):
        builder.add_box(
            (cx - half, cy - half, z0), (cx + half, cy + half, z0 + height), slot
        )
        z0 += height
    builder.add_box((cx - 0.14, cy - 0.14, z0), (cx + 0.14, cy + 0.14, z0 + tip), slot)


def build_bell_tower(
    width: float,
    depth: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
) -> MeshBuilder:
    """西端方形钟塔；z=0 为地面，塔顶自 h2 起参差崩缺。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:tower")
    t = TOWER_WALL_T
    stage = height * 0.60
    belfry = height * 0.895
    wall_top = belfry + 0.16

    # 四面塔身：相对的两面共用同一块网格
    wide = _tower_face(width, wall_top, stage, belfry, tiles)
    narrow = _tower_face(depth, wall_top, stage, belfry, tiles)
    faces = (
        (wide, (0.0, 0.0, 0.0), 0.0),
        (wide, (width, depth + 0.01, 0.0), math.pi),
        (narrow, (-0.01, depth, 0.0), -math.pi / 2),
        (narrow, (width + 0.01, 0.0, 0.0), math.pi / 2),
    )
    for mesh, location, rotation in faces:
        # 各自先旋转到世界位置后再合并，保持单件网格
        placed = MeshBuilder(tiles)
        cos_r, sin_r = math.cos(rotation), math.sin(rotation)
        for x, y, z in mesh.verts:
            placed.verts.append(
                (location[0] + x * cos_r - y * sin_r, location[1] + x * sin_r + y * cos_r, z)
            )
        placed.faces = mesh.faces
        placed.face_slots = mesh.face_slots
        placed.face_uvs = mesh.face_uvs
        _merge(builder, placed)

    # 塔基：一圈略宽的座石
    builder.add_box((-0.16, -0.16, 0.0), (width + 0.16, depth + 0.16, 0.62), "stone")
    builder.add_box((-0.08, -0.08, 0.62), (width + 0.08, depth + 0.08, 0.78), "stone")

    # 转角壁柱与阶梯状的扶壁墩
    for px in (0.0, width):
        for py in (0.0, depth):
            builder.add_box((px - 0.34, py - 0.34, 0.78), (px + 0.34, py + 0.34, stage * 0.52), "stone")
            builder.add_box((px - 0.26, py - 0.26, stage * 0.52), (px + 0.26, py + 0.26, stage + 0.30), "stone")
            builder.add_box((px - 0.30, py - 0.30, stage + 0.30), (px + 0.30, py + 0.30, stage + 0.46), "stone")
            # 上段通高的薄壁柱
            builder.add_box((px - 0.24, py - 0.24, stage + 0.46), (px + 0.24, py + 0.24, wall_top), "stone")

    # 层间线脚
    for z in (stage, belfry):
        builder.add_box((-0.12, -0.10, z), (width + 0.12, t + 0.02, z + 0.16), "stone")
        builder.add_box((-0.12, depth - t - 0.02, z), (width + 0.12, depth + 0.10, z + 0.16), "stone")
        builder.add_box((-0.10, -0.12, z), (t + 0.02, depth + 0.12, z + 0.16), "stone")
        builder.add_box((width - t - 0.02, -0.12, z), (width + 0.10, depth + 0.12, z + 0.16), "stone")

    # 塔顶残存的女儿墙：分段高低不一，随机留缺口
    for origin, axis, span in (
        ((0.0, 0.0), "x", width),
        ((0.0, depth), "x", width),
        ((0.0, 0.0), "y", depth),
        ((width, 0.0), "y", depth),
    ):
        step = 0.52
        count = max(3, int(round(span / step)))
        for index in range(count):
            if rnd.random() < 0.26:
                continue
            a = span * index / count
            b = span * (index + 1) / count
            if axis == "x":
                x0, x1 = origin[0] + a, origin[0] + b
                y0, y1 = origin[1] - 0.02, origin[1] + t + 0.02
            else:
                x0, x1 = origin[0] - 0.02, origin[0] + t + 0.02
                y0, y1 = origin[1] + a, origin[1] + b
            top = belfry + 0.14 + rnd.uniform(0.06, 0.62)
            builder.add_box((x0, y0, belfry + 0.14), (x1, y1, top), "stone")

    # 四角小尖塔：高度各不相同，有一座几乎完全断掉
    tips = [rnd.uniform(0.42, 0.86), rnd.uniform(0.20, 0.52)]
    for px in (0.0, width):
        for py in (0.0, depth):
            tip = rnd.choice(tips)
            if rnd.random() < 0.18:
                tip = rnd.uniform(0.03, 0.10)
            _corner_pinnacle(builder, px, py, belfry + 0.10, tip, "stone")

    # 钟室楼板：从百叶窗往里看是深色的石台，而不是直通到底
    floor_z = stage - 0.24
    _patch(
        builder,
        [
            (t, t, floor_z),
            (width - t, t, floor_z),
            (width - t, depth - t, floor_z),
            (t, depth - t, floor_z),
        ],
        (0.0, 0.0, 1.0),
        0.22,
        "stone",
        (True, True, True, True),
    )
    # 塔心暗部：让成对百叶窗与下部枪眼读成深洞，而不是能看穿的空壳
    inner = 0.66
    builder.add_box(
        (inner, inner, 0.4),
        (width - inner, depth - inner, belfry - 0.10),
        "char",
    )
    return builder


# --------------------------------------------------------------------------- 纵向坡顶
def _nave_slope(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    eave_y: float,
    cy: float,
    z_top: float,
    rise: float,
    thickness: float,
    sign: float,
    ruin: float,
    rnd: random.Random,
    roof_slot: str,
    timber_slot: str,
) -> None:
    """一侧坡面：稀疏残存的石板 + 密排椽条 + 檩条。"""
    half = abs(cy - eave_y)
    length = math.hypot(half, rise)
    normal = (0.0, -sign * rise / length, half / length)
    inward = (-normal[0] * thickness, -normal[1] * thickness, -normal[2] * thickness)

    def point(u: float, v: float) -> tuple[float, float, float]:
        return (u, eave_y + sign * half * v, z_top + rise * v)

    rows = (0.0, 0.30, 0.57, 0.80, 1.0)
    span = x1 - x0
    columns = max(4, int(round(span / 1.02)))
    edges = [x0]
    for index in range(1, columns):
        edges.append(x0 + span * index / columns + rnd.uniform(-0.14, 0.14))
    edges.append(x1)
    edges = sorted(edges)

    # 先在大尺度上划出塌陷区，再在区外整片保留：
    # 残存瓦面因此是成片的大张石板，塌口里只剩零星碎板，而不是均匀的碎麻点。
    density = 0.4 + 0.6 * min(max(ruin, 0.0), 1.0)
    row_count = len(rows) - 1
    holes: list[tuple[int, int, int, int]] = []
    for _ in range(rnd.randint(2, 3)):
        hole_w = rnd.randint(2, min(3, max(2, columns - 1)))
        hole_h = rnd.randint(2, min(3, max(2, row_count - 1)))
        hx = rnd.randint(0, max(0, columns - hole_w))
        hz = rnd.randint(0, max(0, row_count - hole_h))
        holes.append((hx, hx + hole_w, hz, hz + hole_h))

    def in_hole(col: int, row: int) -> bool:
        return any(hx0 <= col < hx1 and hz0 <= row < hz1 for hx0, hx1, hz0, hz1 in holes)

    solid: dict[tuple[int, int], bool] = {}
    for col in range(columns):
        for row in range(row_count):
            if in_hole(col, row):
                # 塌口里残存的碎板：越靠檐口越容易挂住
                chance = (0.26, 0.16, 0.10, 0.08)[row] * density
            else:
                chance = 0.97
                if row == 0:
                    chance = 1.0
                # 塌口边缘啃掉几块，避免整齐的矩形边
                if any(in_hole(col + dx, row + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    chance *= 0.62
                if rnd.random() < 0.06:
                    chance *= 0.5
            solid[(col, row)] = rnd.random() < chance

    def is_solid(col: int, row: int) -> bool:
        if 0 <= col < columns and 0 <= row < len(rows) - 1:
            return solid[(col, row)]
        return False

    for col in range(columns):
        u0, u1 = edges[col], edges[col + 1]
        if u1 - u0 < 0.05:
            continue
        for row in range(len(rows) - 1):
            if not solid[(col, row)]:
                continue
            v0, v1 = rows[row], rows[row + 1]
            corners = [
                point(u0, v0),
                point(u1, v0),
                point(u1, v1),
                point(u0, v1),
            ]
            # 屋脊一侧不补侧壁：两坡在这里相交，补了会出现朝内的重复面
            exposed = (
                not is_solid(col - 1, row),
                not is_solid(col + 1, row),
                not is_solid(col, row - 1),
                row < len(rows) - 2 and not is_solid(col, row + 1),
            )
            _patch(builder, corners, normal, thickness, roof_slot, exposed)

    # 椽条：沿坡向铺满，檐口探出一小段椽尾
    inward_unit = (-normal[0], -normal[1], -normal[2])
    rafter_gap = 0.42
    count = max(3, int(round(span / rafter_gap)))
    rafter_offset = thickness + 0.10

    def inset(vertex: tuple[float, float, float], distance: float):
        return (
            vertex[0] + inward_unit[0] * distance,
            vertex[1] + inward_unit[1] * distance,
            vertex[2] + inward_unit[2] * distance,
        )

    for index in range(count + 1):
        u = x0 + span * index / count
        p0 = inset(point(u, -0.16 / length), rafter_offset)
        p1 = inset(point(u, 1.0), rafter_offset)
        _beam(builder, p0, p1, (1.0, 0.0, 0.0), normal, 0.085, 0.13, timber_slot)

    # 檩条：沿长轴压在椽条下，端头从山墙挑出
    for v, width_b, height_b in ((0.66, 0.11, 0.15), (0.92, 0.13, 0.18)):
        base = inset(point(x0, v), thickness + 0.19)
        p0 = (x0, base[1], base[2])
        p1 = (x1, base[1], base[2])
        _beam(builder, p0, p1, (0.0, 1.0, 0.0), normal, width_b, height_b, timber_slot)

    # 脊梁：压在两坡交接处，破洞处能直接看到
    ridge_z = z_top + rise
    _beam(
        builder,
        (x0, cy, ridge_z - 0.11),
        (x1, cy, ridge_z - 0.11),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        0.20,
        0.24,
        timber_slot,
    )


def build_nave_roof(
    x0: float,
    x1: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
    ruin: float = 0.8,
    seed: int = 42,
    roof_slot: str = "roof",
    timber_slot: str = "trim",
) -> MeshBuilder:
    """屋脊沿长轴的残破双坡顶；x0/x1 为长轴范围，含两端挑出。"""
    builder = MeshBuilder(tiles)
    half = (depth + 2.0 * overhang) * 0.5
    cy = depth * 0.5
    rise = math.tan(math.radians(pitch_deg)) * half
    z_top = z + thickness
    for sign, eave_y in ((1.0, -overhang), (-1.0, depth + overhang)):
        _nave_slope(
            builder,
            x0,
            x1,
            eave_y,
            cy,
            z_top,
            rise,
            thickness,
            sign,
            ruin,
            random.Random(f"{seed}:nave:{sign}"),
            roof_slot,
            timber_slot,
        )
    return builder


# --------------------------------------------------------------------------- 破损山墙
def build_broken_gable(
    depth: float,
    half: float,
    rise: float,
    eave_lift: float,
    thickness: float,
    tiles: dict[str, float],
    seed: int = 42,
    slot: str = "facade",
) -> MeshBuilder:
    """落在端墙顶上的山墙：顶边随屋面收尖，但被削出参差的崩口。

    局部坐标：x 沿进深 0..depth，y 为厚度（0 为外表面），z 自墙顶起算。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:gable")
    strips = max(5, int(round(depth / 0.42)))
    for index in range(strips):
        x0 = depth * index / strips
        x1 = depth * (index + 1) / strips
        cx = (x0 + x1) * 0.5
        profile = eave_lift + rise * max(0.0, 1.0 - abs(cx - depth * 0.5) / half)
        roll = rnd.random()
        if roll < 0.44:
            top = profile
        elif roll < 0.74:
            top = profile - rnd.uniform(0.06, 0.24)
        elif roll < 0.93:
            top = profile - rnd.uniform(0.30, 0.68)
        else:
            top = profile - rnd.uniform(0.85, 1.30)
        # 两端贴着前后立面，保留多一点，山尖才立得住
        if min(cx, depth - cx) < 0.7:
            top = max(top, profile - 0.14)
        top = max(top, 0.22)
        pad = 0.0015
        builder.add_box((x0 - pad, 0.0, -0.03), (x1 + pad, thickness, top), slot)
        # 崩口上方零星的残石
        if top > 0.6 and rnd.random() < 0.55:
            width = min(x1 - x0, rnd.uniform(0.12, 0.26))
            tx = rnd.uniform(x0, max(x0, x1 - width))
            builder.add_box(
                (tx, -0.035, top - 0.05),
                (tx + width, thickness + rnd.uniform(0.0, 0.03), top + rnd.uniform(0.07, 0.22)),
                slot,
            )
    return builder
